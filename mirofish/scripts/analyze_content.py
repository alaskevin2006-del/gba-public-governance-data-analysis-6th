#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
内容立场分类：把真实动作按"谣言放大 / 辟谣与求证 / 中性"分类

为什么需要它：
  A/B 两组的"总互动量"不能直接比较 —— 官方辟谣本身也会引发讨论，
  互动量上升不等于谣言扩散更广。必须把两类内容拆开。

方法：关键词启发式规则（可复现、可审计）
  ⚠️ 局限：关键词法无法识别反讽、引用式否定（如"这是谣言"含"谣言"二字）。
     因此本结果仅作探索性描述，不能作为因果结论。

输出：<组目录>/content_stance.csv（逐轮）与 content_stance_summary.json
"""
import csv
import json
import os
import sys
from collections import defaultdict

# 判定优先级：先判辟谣/求证，再判谣言放大，其余为中性
# 2026-10-21 修订：移除「权威」「官方通报」等弱特征词。
#   实测发现"为什么到现在还没有官方通报""把视频顶上去"这类**质疑官方**的谣言帖
#   会被弱特征词误判为辟谣类，系统性低估谣言类内容。
#   现只保留能直接指向"澄清 / 否定该谣言"的强特征词。
DEBUNK_KW = [
    "情况通报", "辟谣", "虚假", "造假", "AI合成", "AI生成", "ai合成", "ai生成",
    "行政拘留", "不信谣", "不传谣", "勿信", "勿传", "别传", "别信", "谣言",
    "查处", "依法", "警方通报", "不实", "伪造", "经核实", "已核实", "系谣",
]
RUMOR_KW = [
    "坠楼", "塌", "淹", "瞒报", "断供", "被困", "死", "伤亡",
    "太吓人", "恐怖", "完了", "危险", "千万别出门", "顶上去", "扩散",
]

# 仅统计这两类"内容型"动作（点赞无文本，不参与立场分类）
CONTENT_ACTIONS = {"CREATE_POST", "CREATE_COMMENT", "QUOTE_POST"}


def classify(text: str) -> str:
    if not text:
        return "neutral"
    low = text.lower()
    if any(k.lower() in low for k in DEBUNK_KW):
        return "debunk"
    if any(k in text for k in RUMOR_KW):
        return "rumor"
    return "neutral"


def analyze(group_dir: str) -> dict:
    per_round = defaultdict(lambda: {"rumor": 0, "debunk": 0, "neutral": 0})
    examples = {"rumor": [], "debunk": []}

    for plat in ("twitter_actions.jsonl", "reddit_actions.jsonl"):
        p = os.path.join(group_dir, plat)
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("action_type") not in CONTENT_ACTIONS:
                continue
            args = d.get("action_args") or {}
            content = args.get("content") or args.get("comment_content") or ""
            stance = classify(str(content))
            per_round[d.get("round", 0)][stance] += 1
            if stance in examples and len(examples[stance]) < 5:
                examples[stance].append(str(content)[:70])

    rows = []
    cum_r = cum_d = 0
    for r in sorted(per_round):
        d = per_round[r]
        cum_r += d["rumor"]
        cum_d += d["debunk"]
        rows.append({
            "round": r,
            "rumor_content": d["rumor"],
            "debunk_content": d["debunk"],
            "neutral_content": d["neutral"],
            "cumulative_rumor": cum_r,
            "cumulative_debunk": cum_d,
        })

    out_csv = os.path.join(group_dir, "content_stance.csv")
    if rows:
        with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            for row in rows:
                w.writerow(row)

    summary = {
        "rounds": len(rows),
        "rumor_total": sum(r["rumor_content"] for r in rows),
        "debunk_total": sum(r["debunk_content"] for r in rows),
        "neutral_total": sum(r["neutral_content"] for r in rows),
        "examples": examples,
    }
    with open(os.path.join(group_dir, "content_stance_summary.json"), "w",
              encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


if __name__ == "__main__":
    for d in sys.argv[1:]:
        s = analyze(d)
        print(f"\n=== {os.path.basename(d)} ===")
        print(json.dumps({k: v for k, v in s.items() if k != "examples"},
                         ensure_ascii=False, indent=2))
