#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从 MiroFish 真实动作日志 actions.jsonl 提取逐轮互动指标

数据源：uploads/simulations/<sim_id>/{twitter,reddit}/actions.jsonl
  真实字段（已实测）：
    - {"round", "event_type": "round_start", "simulated_hour"}
    - {"round", "agent_id", "agent_name", "action_type", "action_args", "result", "success"}
    - {"round", "event_type": "round_end", "actions_count"}

为什么不用 timeline：timeline 只记录"有动作的轮"，会漏掉空轮，
导致"实际跑 2 轮但只解析出 1 轮"。actions.jsonl 有 round_start/round_end 标记，
能还原完整轮次序列，空轮也保留（计数为 0）。

输出 per_round_actions.csv：
  round, simulated_hour, posts, comments, reposts, likes, other,
  total_actions, interactions(不含 DO_NOTHING/REFRESH), active_agents,
  cumulative_interactions
"""
import csv
import json
import os
import sys
from collections import defaultdict

# 动作归类（按真实出现的 action_type 归类，不编造未知类型）
CATEGORY = {
    "CREATE_POST": "posts",
    "CREATE_COMMENT": "comments",
    "REPOST": "reposts",
    "QUOTE_POST": "reposts",
    "LIKE_POST": "likes",
    "DISLIKE_POST": "likes",
    "LIKE_COMMENT": "likes",
    "DISLIKE_COMMENT": "likes",
}
NON_INTERACTION = {
    "DO_NOTHING", "REFRESH", "SEARCH_POSTS", "SEARCH_USER", "TREND", "MUTE", "INTERVIEW",
}


def read_actions(path: str):
    """返回 (rounds_meta, actions)"""
    rounds_meta = {}
    actions = []
    if not os.path.exists(path):
        return rounds_meta, actions
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            et = d.get("event_type")
            if et == "round_start":
                rounds_meta[d.get("round")] = d.get("simulated_hour")
            elif et in ("round_end", "simulation_start", "simulation_end"):
                continue
            elif d.get("action_type"):
                actions.append(d)
    return rounds_meta, actions


def aggregate(result_dir: str, out_csv: str = None) -> dict:
    tw_meta, tw_act = read_actions(os.path.join(result_dir, "twitter_actions.jsonl"))
    rd_meta, rd_act = read_actions(os.path.join(result_dir, "reddit_actions.jsonl"))

    all_meta = dict(tw_meta)
    all_meta.update(rd_meta)
    all_actions = tw_act + rd_act

    per_round = defaultdict(lambda: {k: 0 for k in
                                     ("posts", "comments", "reposts", "likes", "other")})
    per_round["__agents__"] = defaultdict(set)
    unknown = defaultdict(int)

    for a in all_actions:
        r = a.get("round", 0)
        at = a.get("action_type", "")
        cat = CATEGORY.get(at)
        if at in NON_INTERACTION:
            cat = None  # 不计入互动，但也不算 unknown
        elif cat is None:
            cat = "other"
            unknown[at] += 1
        if cat:
            per_round[r][cat] += 1
        if a.get("agent_id") is not None and at not in NON_INTERACTION:
            per_round["__agents__"][r].add(a["agent_id"])

    agents_map = per_round.pop("__agents__")
    rounds = sorted(set(all_meta.keys()) | set(per_round.keys()))

    rows = []
    cum = 0
    for r in rounds:
        d = per_round.get(r, {"posts": 0, "comments": 0, "reposts": 0, "likes": 0, "other": 0})
        interactions = d["posts"] + d["comments"] + d["reposts"] + d["likes"]
        total = interactions + d["other"]
        cum += interactions
        rows.append({
            "round": r,
            "simulated_hour": all_meta.get(r, ""),
            "posts": d["posts"],
            "comments": d["comments"],
            "reposts": d["reposts"],
            "likes": d["likes"],
            "other_actions": d["other"],
            "interactions": interactions,
            "total_actions": total,
            "active_agents": len(agents_map.get(r, ())),
            "cumulative_interactions": cum,
        })

    out_csv = out_csv or os.path.join(result_dir, "per_round_actions.csv")
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else
                           ["round", "simulated_hour", "posts", "comments", "reposts",
                            "likes", "other_actions", "interactions", "total_actions",
                            "active_agents", "cumulative_interactions"])
        w.writeheader()
        for row in rows:
            w.writerow(row)

    summary = {
        "rounds": len(rows),
        "total_interactions": sum(r["interactions"] for r in rows),
        "posts": sum(r["posts"] for r in rows),
        "comments": sum(r["comments"] for r in rows),
        "reposts": sum(r["reposts"] for r in rows),
        "likes": sum(r["likes"] for r in rows),
        "unique_agents": len({a for s in agents_map.values() for a in s}),
        "peak_round": (max(rows, key=lambda r: r["interactions"])["round"] if rows else None),
        "peak_interactions": (max(r["interactions"] for r in rows) if rows else 0),
        "unknown_action_types": dict(unknown),
    }
    return {"rows": rows, "summary": summary, "csv": out_csv}


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if target and os.path.isfile(os.path.join(target, "twitter_actions.jsonl")):
        res = aggregate(target)
        print(json.dumps(res["summary"], ensure_ascii=False, indent=2))
        print("->", res["csv"])
    else:
        # 批量：对 results 下所有含 actions 的组目录处理
        root = target or os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "results")
        for name in sorted(os.listdir(root)):
            d = os.path.join(root, name)
            if not os.path.isdir(d):
                continue
            for sub in ([d] + [os.path.join(d, s) for s in ("A", "B", "C")]):
                if os.path.exists(os.path.join(sub, "twitter_actions.jsonl")):
                    res = aggregate(sub)
                    print(f"\n=== {os.path.basename(os.path.dirname(sub))}/{os.path.basename(sub)} ===")
                    print(json.dumps(res["summary"], ensure_ascii=False, indent=2))
