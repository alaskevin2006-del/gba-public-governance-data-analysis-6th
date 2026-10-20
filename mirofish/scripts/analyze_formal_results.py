#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
正式实验结果汇总分析（全部指标来自真实 actions.jsonl）

可计算的真实指标（不可计算的绝不推测）：
  1. 逐轮互动量：发帖 / 评论 / 点赞（含点踩） / 转发缺失情况如实记录
  2. 逐轮内容立场：谣言放大类 vs 辟谣求证类 vs 中性（关键词启发式，已留样核）
  3. 互动指向性：LIKE_POST/DISLIKE_POST/LIKE_COMMENT 的 action_args 中带有
     被互动对象的文本（post_content / comment_content），可区分
     "对谣言内容的互动" 与 "对官方辟谣内容的互动"
  4. 参与广度：产出某类内容的去重 Agent 数
  5. 峰值与达峰轮次、累计规模、干预前后分段指标

不可得（如实记录为局限）：
  · 转发关系链：Twitter 的 REPOST 计数为 0，Reddit 无转发动作；
    且 CREATE_COMMENT 的 action_args 不含被评论对象 → 无法重建传播树。
  · 恐慌率 / 囤货率 / 信任度：无对应字段，不予量化。
"""
import csv
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_actions as pa
import analyze_content as ac
import formal_experiment_config as fc

CONTENT_ACTIONS = {"CREATE_POST", "CREATE_COMMENT", "QUOTE_POST"}
TARGET_ACTIONS = {"LIKE_POST", "DISLIKE_POST", "LIKE_COMMENT", "DISLIKE_COMMENT"}


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("action_type"):
                out.append(d)
            elif d.get("event_type") == "round_start":
                out.append(d)
    return out


def collect_rows(result_dir):
    rows = []
    rounds_hour = {}
    for plat in ("twitter_actions.jsonl", "reddit_actions.jsonl"):
        for d in read_jsonl(os.path.join(result_dir, plat)):
            if d.get("event_type") == "round_start":
                rounds_hour[d.get("round")] = d.get("simulated_hour")
                continue
            rows.append((plat.replace("_actions.jsonl", ""), d))
    return rows, rounds_hour


def analyze_run(run_dir, meta):
    rows, rounds_hour = collect_rows(run_dir)
    intervention = meta.get("intervention")
    inj_round = meta.get("intervention_round")
    marker = fc.INTERVENTION_MARKERS.get(intervention) if intervention else None

    per_round = defaultdict(lambda: {
        "posts": 0, "comments": 0, "reposts": 0, "likes": 0,
        "content_rumor": 0, "content_debunk": 0, "content_neutral": 0,
        "engage_rumor": 0, "engage_debunk": 0, "engage_other": 0,
    })
    agents_rumor = set()
    agents_debunk = set()
    agents_any = set()

    for plat, d in rows:
        r = d.get("round", 0)
        at = d.get("action_type", "")
        agent = d.get("agent_id")
        args = d.get("action_args") or {}
        rec = per_round[r]

        # 动作计数
        cat = pa.CATEGORY.get(at)
        if at in pa.NON_INTERACTION:
            cat = None
        elif cat is None:
            cat = "other"
        if cat in ("posts", "comments", "reposts", "likes"):
            rec[cat] += 1
            if agent is not None:
                agents_any.add(agent)

        # 内容立场
        if at in CONTENT_ACTIONS:
            text = str(args.get("content") or args.get("comment_content") or "")
            stance = ac.classify(text)
            key = {"rumor": "content_rumor", "debunk": "content_debunk",
                   "neutral": "content_neutral"}[stance]
            rec[key] += 1
            if stance == "rumor" and agent is not None:
                agents_rumor.add(agent)
            if stance == "debunk" and agent is not None:
                agents_debunk.add(agent)

        # 互动指向性（依据被互动对象的文本）
        if at in TARGET_ACTIONS:
            target = str(args.get("post_content") or args.get("comment_content") or "")
            if marker and marker in target:
                rec["engage_debunk"] += 1
            elif not target:
                rec["engage_other"] += 1
            else:
                st = ac.classify(target)
                if st == "rumor":
                    rec["engage_rumor"] += 1
                elif st == "debunk":
                    rec["engage_debunk"] += 1
                else:
                    rec["engage_other"] += 1

    rounds = sorted(set(rounds_hour) | set(per_round))
    out_rows = []
    cum_int = cum_rumor = cum_debunk = 0
    for r in rounds:
        d = per_round.get(r, {k: 0 for k in
                              ("posts", "comments", "reposts", "likes",
                               "content_rumor", "content_debunk", "content_neutral",
                               "engage_rumor", "engage_debunk", "engage_other")})
        interactions = d["posts"] + d["comments"] + d["reposts"] + d["likes"]
        cum_int += interactions
        cum_rumor += d["content_rumor"]
        cum_debunk += d["content_debunk"]
        out_rows.append({
            "round": r,
            "simulated_hour": rounds_hour.get(r, ""),
            "posts": d["posts"], "comments": d["comments"],
            "reposts": d["reposts"], "likes": d["likes"],
            "interactions": interactions,
            "cumulative_interactions": cum_int,
            "content_rumor": d["content_rumor"],
            "content_debunk": d["content_debunk"],
            "content_neutral": d["content_neutral"],
            "engage_rumor": d["engage_rumor"],
            "engage_debunk": d["engage_debunk"],
            "engage_other": d["engage_other"],
            "cumulative_content_rumor": cum_rumor,
            "cumulative_content_debunk": cum_debunk,
            "phase": ("pre" if inj_round and r < inj_round
                      else ("post" if inj_round and r >= inj_round else "none")),
        })

    csv_path = os.path.join(run_dir, "metrics_per_round.csv")
    if out_rows:
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
            w.writeheader()
            w.writerows(out_rows)

    def s(key):
        return sum(row[key] for row in out_rows)

    peak_row = max(out_rows, key=lambda x: x["interactions"]) if out_rows else None
    post_rows = [x for x in out_rows if x["phase"] == "post"]
    pre_rows = [x for x in out_rows if x["phase"] == "pre"]

    metrics = {
        "run": meta.get("run_name"),
        "group": meta.get("group"),
        "rep": meta.get("rep"),
        "exp": meta.get("exp"),
        "group_name": meta.get("group_name"),
        "rounds": len(out_rows),
        "n_agents": meta.get("n_agents"),
        "intervention": intervention or "NONE",
        "intervention_round": inj_round,
        "interaction_verify": meta.get("intervention_verify", {}),
        "random_seed": meta.get("random_seed"),
        "elapsed_sec": meta.get("elapsed_sec"),
        "total_interactions": s("interactions"),
        "total_posts": s("posts"),
        "total_comments": s("comments"),
        "total_reposts": s("reposts"),
        "total_likes": s("likes"),
        "content_rumor": s("content_rumor"),
        "content_debunk": s("content_debunk"),
        "content_neutral": s("content_neutral"),
        "engage_rumor": s("engage_rumor"),
        "engage_debunk": s("engage_debunk"),
        "agents_active": len(agents_any),
        "agents_rumor_content": len(agents_rumor),
        "agents_debunk_content": len(agents_debunk),
        "peak_round": peak_row["round"] if peak_row else None,
        "peak_interactions": peak_row["interactions"] if peak_row else 0,
        "post_window_interactions": sum(x["interactions"] for x in post_rows),
        "post_window_rumor_content": sum(x["content_rumor"] for x in post_rows),
        "post_window_debunk_content": sum(x["content_debunk"] for x in post_rows),
        "pre_window_interactions": sum(x["interactions"] for x in pre_rows),
        "pre_window_rumor_content": sum(x["content_rumor"] for x in pre_rows),
        "balance_before": meta.get("balance_before"),
        "balance_after": meta.get("balance_after"),
    }
    # 单位：谣言相关互动 = 谣言类内容 + 指向谣言内容的互动
    metrics["rumor_related_actions"] = metrics["content_rumor"] + metrics["engage_rumor"]
    with open(os.path.join(run_dir, "run_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    return out_rows, metrics


FIELDS = None


def write_tidy(out_root, all_series, all_metrics):
    os.makedirs(os.path.join(out_root, "summary"), exist_ok=True)
    # 逐行长表（绘图用）
    tidy_path = os.path.join(out_root, "summary", "per_round_long.csv")
    fields = None
    with open(tidy_path, "w", newline="", encoding="utf-8-sig") as f:
        w = None
        for name, rows in all_series.items():
            for row in rows:
                rec = {"condition": name}
                rec.update(row)
                if fields is None:
                    fields = list(rec.keys())
                    w = csv.DictWriter(f, fieldnames=fields)
                    w.writeheader()
                w.writerow(rec)
    # 每次运行的指标总表
    m_path = os.path.join(out_root, "summary", "all_runs_metrics.csv")
    if all_metrics:
        with open(m_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(all_metrics[0].keys()))
            w.writeheader()
            for m in all_metrics:
                w.writerow(m)
    return tidy_path, m_path


def aggregate_by_condition(all_metrics):
    """按条件聚合（重复次数少，只给均值与极差，不做统计检验）。"""
    buckets = defaultdict(list)
    for m in all_metrics:
        buckets[m["group"]].append(m)
    out = []
    keys = ["total_interactions", "total_posts", "total_comments", "total_likes",
            "content_rumor", "content_debunk", "engage_rumor", "engage_debunk",
            "rumor_related_actions", "agents_rumor_content", "agents_debunk_content",
            "peak_interactions", "post_window_interactions",
            "post_window_rumor_content", "post_window_debunk_content"]
    for g, ms in buckets.items():
        row = {"group": g,
               "group_name": ms[0]["group_name"],
               "exp": ms[0]["exp"],
               "intervention": ms[0]["intervention"],
               "intervention_round": ms[0]["intervention_round"],
               "n_reps": len(ms)}
        for k in keys:
            vals = [m[k] for m in ms]
            row[f"{k}_mean"] = round(sum(vals) / len(vals), 2)
            row[f"{k}_min"] = min(vals)
            row[f"{k}_max"] = max(vals)
        peaks = [m["peak_round"] for m in ms if m["peak_round"] is not None]
        row["peak_round_values"] = ";".join(str(p) for p in peaks)
        out.append(row)
    return out


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else None
    root = root or os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "results", "formal_20261021")
    runs_dir = os.path.join(root, "runs")
    if not os.path.isdir(runs_dir):
        raise SystemExit(f"找不到运行目录: {runs_dir}")

    all_series, all_metrics = {}, []
    for name in sorted(os.listdir(runs_dir)):
        d = os.path.join(runs_dir, name)
        meta_path = os.path.join(d, "run_meta.json")
        if not os.path.exists(meta_path):
            continue
        meta = json.load(open(meta_path, encoding="utf-8"))
        # 两种编排脚本写出的完成标记不同（API 编排用 file-watch，直连子进程用退出码）
        if meta.get("final_status") not in ("completed(file-watch)", "completed"):
            print(f"[skip] {name} 未完成 ({meta.get('final_status')})")
            continue
        series, m = analyze_run(d, meta)
        all_series[name] = series
        all_metrics.append(m)
        print(f"[ok] {name}: 互动{m['total_interactions']} 谣言类{m['content_rumor']} "
              f"辟谣类{m['content_debunk']} 峰值第{m['peak_round']}轮 "
              f"参与Agent{m['agents_active']}")

    os.makedirs(os.path.join(root, "summary"), exist_ok=True)
    t, mp = write_tidy(root, all_series, all_metrics)
    cond = aggregate_by_condition(all_metrics)
    c_path = os.path.join(root, "summary", "by_condition_metrics.csv")
    if cond:
        with open(c_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(cond[0].keys()))
            w.writeheader()
            w.writerows(cond)
    with open(os.path.join(root, "summary", "analysis_manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump({"n_runs": len(all_metrics),
                   "conditions": sorted({m["group"] for m in all_metrics}),
                   "tidy_csv": t, "metrics_csv": mp, "condition_csv": c_path},
                  f, ensure_ascii=False, indent=2)
    print(f"\n-> {mp}\n-> {c_path}\n-> {t}")


if __name__ == "__main__":
    main()
