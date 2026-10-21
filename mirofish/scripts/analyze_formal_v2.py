#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
正式实验指标计算 v2（去重版）

相对 v1 的修正（均为 2026-10-21 复核发现）：
 1. **初始帖重复计数**：4 条研究者注入的初始谣言帖在 round 0 与 round 1 各被记录一次，
    v1 把两者都算进了"自发互动"。现以 round 0 为**初始态**（不计入自发互动），
    并在 round>=1 中剔除与 round 0 完全同作者同内容的重复记录。
 2. **round 0 不是模拟轮**：round 0 只有研究者注入的初始帖，属实验初始条件而非 Agent 自主行为，
    现单列为 initial_state，不参与任何"互动/传播"指标。
 3. **内容立场分类换用 content_classifier_v2**（见该脚注：修正了官方通报被判为谣言、
    反悔式劝阻被判为谣言、实际扩散行为被判为中性等三类系统性错误）。
 4. **时间标签显式化**：round / hour_index(0基) / hour_1idx(第 k 模拟小时) / elapsed 分钟区间
    同时输出，消除"第 4 模拟小时"这类表述的歧义。
 5. **固定观察窗**：为支持不同介入时点之间的可比比较，统一取「介入轮 k 起连续 POST_WINDOW 轮」
    作为干预后固定窗口（缺一时间：-1 表示不足）。

用法：
  python analyze_formal_v2.py <run_dir> [<run_dir> ...]
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import content_classifier_v2 as C

POST_WINDOW = 5  # 固定介入后观察窗（轮）

COUNTABLE_INTERACTIONS = {
    "CREATE_POST", "CREATE_COMMENT", "QUOTE_POST", "REPOST",
    "LIKE_POST", "DISLIKE_POST", "LIKE_COMMENT", "DISLIKE_COMMENT",
}
NON_INTERACTIVE = {"DO_NOTHING", "REFRESH", "SEARCH_POSTS", "SEARCH_USER",
                   "TREND", "MUTE", "FOLLOW"}


def load_actions(path):
    """返回 (actions, hour_map, errors)"""
    actions, hour_map, errors = [], {}, []
    for i, line in enumerate(open(path, encoding="utf-8", errors="ignore")):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception as e:
            errors.append((i, str(e)))
            continue
        et = d.get("event_type")
        if et == "round_start":
            hour_map[int(d["round"])] = int(d.get("simulated_hour", -1))
            continue
        if et in ("round_end", "simulation_start", "simulation_end"):
            continue
        if "action_type" in d:
            actions.append(d)
    return actions, hour_map, errors


def target_text(args):
    for k in ("post_content", "comment_content"):
        v = args.get(k)
        if v:
            return str(v)
    return ""


def main():
    out_index = {}
    for run_dir in sys.argv[1:]:
        name = os.path.basename(run_dir.rstrip("\\/"))
        reddit = os.path.join(run_dir, "reddit_actions.jsonl")
        if not os.path.exists(reddit):
            print(f"[skip] {name}: 无 reddit_actions.jsonl")
            continue
        actions, hour_map, errors = load_actions(reddit)

        # ---- 初始态 round 0 ----
        initial = [a for a in actions if a.get("round") == 0]
        init_keys = {(a.get("agent_name"), (a.get("action_args") or {}).get("content"))
                     for a in initial}
        init_labels = Counter()
        for a in initial:
            c = str((a.get("action_args") or {}).get("content") or "")
            init_labels[C.classify(c)] += 1

        # ---- 自发轮次 round >= 1，剔除重复初始帖 ----
        n_dropped = 0
        rows, labels = [], []
        for r in sorted(set(a.get("round") for a in actions if (a.get("round") or 0) >= 1)):
            rs = [a for a in actions if a.get("round") == r]
            kept = []
            for a in rs:
                k = (a.get("agent_name"), (a.get("action_args") or {}).get("content"))
                if k in init_keys:
                    n_dropped += 1
                    continue
                kept.append(a)

            c = Counter()
            for a in kept:
                at = a.get("action_type")
                args = a.get("action_args") or {}
                if at == "CREATE_POST":
                    c["posts"] += 1
                elif at == "CREATE_COMMENT":
                    c["comments"] += 1
                elif at == "REPOST":
                    c["reposts"] += 1
                elif at in ("LIKE_POST", "DISLIKE_POST", "LIKE_COMMENT", "DISLIKE_COMMENT"):
                    c["likes"] += 1
                elif at == "FOLLOW":
                    c["follow"] += 1
                elif at in NON_INTERACTIVE:
                    c["non_interactive"] += 1

                # 内容立场
                if at in C.CONTENT_ACTIONS:
                    content = str(args.get("content") or args.get("comment_content") or "")
                    lab, ev = C.classify(content, True)
                    c["content_" + lab] += 1
                    labels.append({"round": r, "agent": a.get("agent_name"),
                                   "kind": "content", "label": lab,
                                   "text": content, "evidence": ev})
                # 互动指向
                if at in ("LIKE_POST", "DISLIKE_POST", "LIKE_COMMENT", "DISLIKE_COMMENT"):
                    tt = target_text(args)
                    tlab = C.classify(tt) if tt else "unknown"
                    if tlab == "rumor":
                        c["engage_rumor"] += 1
                    elif tlab == "debunk":
                        c["engage_debunk"] += 1
                    else:
                        c["engage_other"] += 1
                    labels.append({"round": r, "agent": a.get("agent_name"),
                                   "kind": "engage", "label": tlab,
                                   "text": tt, "evidence": {}})

            # c 为 Counter，缺失键自动返回 0
            interactions = (c["posts"] + c["comments"] + c["reposts"] + c["likes"])
            hour_index = hour_map.get(r, r - 1)
            rows.append({
                "round": r,
                "hour_index": hour_index,
                "hour_1idx": hour_index + 1,
                "elapsed_min_start": hour_index * 60,
                "elapsed_min_end": hour_index * 60 + 60,
                "posts": c["posts"], "comments": c["comments"],
                "reposts": c["reposts"], "likes": c["likes"],
                "follow": c["follow"], "non_interactive": c["non_interactive"],
                "interactions": interactions,
                "content_rumor": c["content_rumor"],
                "content_debunk": c["content_debunk"],
                "content_neutral": c["content_neutral"],
                "engage_rumor": c["engage_rumor"],
                "engage_debunk": c["engage_debunk"],
                "engage_other": c["engage_other"],
                "rumor_related": c["content_rumor"] + c["engage_rumor"],
                "debunk_related": c["content_debunk"] + c["engage_debunk"],
            })
        # c 为 Counter，缺键返回 0，但普通 dict 不行 —— 上面用 Counter 没问题

        cum = 0
        for row in rows:
            cum += row["interactions"]
            row["cumulative_interactions"] = cum

        # ---- 窗口指标 ----
        meta_p = os.path.join(run_dir, "run_meta.json")
        meta = json.load(open(meta_p, encoding="utf-8")) if os.path.exists(meta_p) else {}
        k = meta.get("intervention_round")
        total_runs = max(r["round"] for r in rows) if rows else 0

        def window(lo, hi):
            sel = [x for x in rows if lo <= x["round"] <= hi]
            return {
                "rounds": [x["round"] for x in sel],
                "interactions": sum(x["interactions"] for x in sel),
                "rumor_related": sum(x["rumor_related"] for x in sel),
                "debunk_related": sum(x["debunk_related"] for x in sel),
                "content_rumor": sum(x["content_rumor"] for x in sel),
                "engage_rumor": sum(x["engage_rumor"] for x in sel),
            }

        if k:
            post_hi = min(total_runs, k + POST_WINDOW - 1)
            complete = (post_hi - k + 1) == POST_WINDOW
            wins = {
                "pre": window(1, k - 1) if k > 1 else {"rounds": [], "interactions": 0,
                                                       "rumor_related": 0, "debunk_related": 0,
                                                       "content_rumor": 0, "engage_rumor": 0},
                "post_full": window(k, total_runs),
                f"post_{POST_WINDOW}": window(k, post_hi),
                f"post_{POST_WINDOW}_complete": complete,
            }
        else:
            wins = {"pre": {"rounds": [], "interactions": 0, "rumor_related": 0,
                            "debunk_related": 0, "content_rumor": 0, "engage_rumor": 0},
                    "post_full": window(1, total_runs),
                    f"post_{POST_WINDOW}": window(1, POST_WINDOW),
                    f"post_{POST_WINDOW}_complete": True}

        peak = max(rows, key=lambda x: x["rumor_related"]) if rows else None
        summary = {
            "run_name": name,
            "group": meta.get("group"), "rep": meta.get("rep"),
            "status": meta.get("final_status"),
            "n_agents": meta.get("n_agents"),
            "rounds_configured": meta.get("rounds"),
            "rounds_observed": total_runs,
            "random_seed": meta.get("random_seed"),
            "intervention": meta.get("intervention"),
            "intervention_round": k,
            "initial_state": {"n_posts": len(initial),
                              "labels": dict(init_labels)},
            "duplicate_initial_posts_dropped": n_dropped,
            "totals": {key: sum(r[key] for r in rows) for key in
                       ("posts", "comments", "reposts", "likes", "follow",
                        "non_interactive", "interactions", "content_rumor",
                        "content_debunk", "content_neutral", "engage_rumor",
                        "engage_debunk", "engage_other", "rumor_related",
                        "debunk_related")},
            "peak_rumor_related": peak["rumor_related"] if peak else None,
            "peak_round": peak["round"] if peak else None,
            "windows": wins,
            "round_labels": dict(Counter(l["label"] for l in labels if l["kind"] == "content")),
            "engage_labels": dict(Counter(l["label"] for l in labels if l["kind"] == "engage")),
            "parse_errors": len(errors),
            "hour_map": {str(kk): vv for kk, vv in sorted(hour_map.items())},
        }

        with open(os.path.join(run_dir, "metrics_v2.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        with open(os.path.join(run_dir, "metrics_per_round_v2.csv"), "w",
                  newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        with open(os.path.join(run_dir, "content_labels_audit.csv"), "w",
                  newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["round", "agent", "kind", "label", "text"])
            w.writeheader()
            for l in labels:
                w.writerow({kk: l[kk] for kk in ("round", "agent", "kind", "label", "text")})

        out_index[name] = summary
        print(f"[{name}] 状态={summary['status']} 轮={total_runs} "
              f"初始帖={len(initial)}(去除重复{n_dropped}) "
              f"互动={summary['totals']['interactions']} "
              f"谣言相关={summary['totals']['rumor_related']} "
              f"辟谣相关={summary['totals']['debunk_related']}")

    if len(sys.argv) > 2:
        idx = os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), "index_v2.json")
        json.dump(out_index, open(idx, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"\n汇总 -> {idx}")


if __name__ == "__main__":
    main()
