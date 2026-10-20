#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
实验配置覆写（在 prepare 之后、start 之前修改 simulation_config.json）

为什么需要它（2026-10-20 实测诊断）：
  1. 上游 LLM 生成的 agent_configs 会把 active_hours 限制在工作时段
     （如 [9,10,11,14,15,16]），而仿真从 hour 0 开始，导致
     `scripts/run_parallel_simulation.py:1071` 的
     `if current_hour not in active_hours: continue` 全部跳过 → 0 个有机动作
     （上一次运行整个循环仅耗时 0.1 秒，6 条帖全部来自 initial_posts）。
  2. time_config.off_peak_activity_multiplier（0.05）会把凌晨时段活跃度打到极低。
  3. agents_per_hour_min/max 由 LLM 决定，可能低至 1~2。

本模块把这些"活跃度闸门"统一拉起，使 Agent 真正进入 OASIS 动作循环。
所有覆写值都显式记录，便于在论文中说明这是建模假设而非真实校准结果。

⚠️ 诚实声明：这些参数是"为了让传播过程可被观测"而设定的探索性配置，
   不代表经过现实数据校准。A/B 两组使用完全相同的活跃度参数，
   因此组间差异可归因于干预因素本身。
"""
import json
import os
from typing import Any, Dict, List


def load_config(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_config(path: str, cfg: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def enable_interaction(
    cfg: Dict[str, Any],
    activity_level: float = 0.9,
    agents_per_round_min: int = 6,
    agents_per_round_max: int = 10,
) -> Dict[str, Any]:
    """拉开活跃度闸门，使 Agent 能进入动作循环。返回本次实际修改的摘要。"""
    tc = cfg.setdefault("time_config", {})
    agents = cfg.get("agent_configs") or []
    n = len(agents)

    # 每轮激活上限不超过总 Agent 数
    amin = max(1, min(agents_per_round_min, n))
    amax = max(amin, min(agents_per_round_max, n))

    before = {
        "agents_per_hour_min": tc.get("agents_per_hour_min"),
        "agents_per_hour_max": tc.get("agents_per_hour_max"),
        "off_peak_hours": tc.get("off_peak_hours"),
        "peak_hours": tc.get("peak_hours"),
    }

    tc["agents_per_hour_min"] = amin
    tc["agents_per_hour_max"] = amax
    # 清空峰谷时段 → multiplier 恒为 1.0，避免 0.05 倍衰减
    tc["off_peak_hours"] = []
    tc["peak_hours"] = []
    tc["morning_hours"] = []
    tc["work_hours"] = []

    changed_agents = 0
    for a in agents:
        a["active_hours"] = list(range(24))  # 全时段可活动
        a["activity_level"] = activity_level
        a.setdefault("posts_per_hour", 0.5)
        a.setdefault("comments_per_hour", 1.0)
        a["response_delay_min"] = 2
        a["response_delay_max"] = 10
        changed_agents += 1

    return {
        "agents_total": n,
        "agents_modified": changed_agents,
        "agents_per_round": [amin, amax],
        "activity_level": activity_level,
        "before": before,
    }


# ---------------------------------------------------------------- 初始帖子 ---
# 谣言帖内容：严格依据仓库真实材料改写
#   事件见 data/01_official/official_debunks.csv (P1-01) 与 mirofish/seed/seed_main_baihaitun.md §1.2
RUMOR_POSTS = [
    "【紧急扩散】浦东一女子在台风「白海豚」中坠楼！现场视频都传疯了，太吓人了！",
    "刚在业主群里看到的视频，说浦东有人被台风吹下楼了，真的假的？有附近的邻居出来证实一下吗？",
    "台风太猛了！听说浦东已经有人坠楼，地下车库也淹了，大家千万别出门！转发提醒家人！",
    "这种天气还让不让人活了，官方一直不通报伤亡情况，是不是在瞒报？大家顶上去！",
]

# 官方辟谣帖：依据 official_debunks.csv P1-01 定性原话 + 处罚结果
OFFICIAL_DEBUNK_POST = (
    "【情况通报】经属地公安部门调查，网传「浦东一女子在台风中坠楼」系虚假信息。"
    "该视频系网民高某某（男，60岁）为博取流量，运用 AI 软件生成涉台风视频并发布，"
    "造成不良社会影响，目前已被行政拘留。请广大市民不信谣、不传谣，"
    "关注气象部门与应急管理部门发布的权威信息。"
)


def pick_agents(cfg: Dict[str, Any]) -> Dict[str, List[int]]:
    """从 agent_configs 中挑选：可发谣言的公众/个人 Agent，与官方/政务 Agent。"""
    agents = cfg.get("agent_configs") or []
    official_kw = ("警方", "公安", "政府", "官方", "辟谣", "应急", "气象", "发布")
    official, public = [], []
    for a in agents:
        name = str(a.get("entity_name") or "")
        etype = str(a.get("entity_type") or "")
        aid = a.get("agent_id")
        if aid is None:
            continue
        if any(k in name for k in official_kw) or etype.lower() in ("official", "governmentagency"):
            official.append(aid)
        else:
            public.append(aid)
    if not official and agents:
        # 无显式官方实体时，退化为使用第一个 Agent（并记录该退化）
        official = [agents[0]["agent_id"]]
    if not public:
        public = [a["agent_id"] for a in agents]
    return {"official": official, "public": public}


def set_initial_posts(
    cfg: Dict[str, Any],
    include_official_debunk: bool,
    n_rumors: int = 4,
) -> Dict[str, Any]:
    """设定初始帖子。A/B 两组仅差"是否含官方辟谣帖"，其余完全一致。"""
    picked = pick_agents(cfg)
    public, official = picked["public"], picked["official"]
    rumors = RUMOR_POSTS[:n_rumors]

    posts = []
    for i, content in enumerate(rumors):
        aid = public[i % len(public)]
        posts.append({"content": content, "poster_agent_id": aid})

    if include_official_debunk:
        # 官方辟谣由政务 Agent 发布
        posts.append({
            "content": OFFICIAL_DEBUNK_POST,
            "poster_agent_id": official[0],
            "is_official_intervention": True,
        })

    ec = cfg.setdefault("event_config", {})
    removed = ec.get("initial_posts", [])
    ec["initial_posts"] = posts
    # 上游 scheduled_events 恒为 []（源码 _parse_event_config 写死），不做无用功
    ec["scheduled_events"] = []

    return {
        "initial_posts_set": len(posts),
        "rumor_posts": len(rumors),
        "official_debunk_included": include_official_debunk,
        "official_agent_id": official[0] if include_official_debunk else None,
        "removed_llm_generated_posts": len(removed),
        "agent_ids": {"public": public, "official": official},
    }
