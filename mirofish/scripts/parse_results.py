#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
解析 MiroFish 原始导出（raw_export.json）→ 逐轮标准 CSV

【2026-10-20 真实运行校准 @7657031】
真实字段（已用 sim_5379ef9a11b5 实跑验证）与早期假设不同，本脚本按真实结构调整：

  1. posts / comments **没有 round 字段**，只有 `created_at`（模拟分钟，int）。
     → 逐轮轮次不能直接从帖子取，必须以 `timeline[].round_num` 为主索引。
  2. timeline 记录了每轮的：total_actions / twitter_actions / reddit_actions /
     action_types{dict} / active_agents[list] / first_action_time / last_action_time。
     → 这是唯一可靠的逐轮来源。
  3. 帖子互动字段为 num_likes / num_dislikes / num_shares / num_reports / num_comments，
     而非 like_count / repost_count。
  4. 已知上游缺陷：timeline 的 rounds_count 可能小于实际轮数（本次 2 轮只记录 1 轮），
     CSV 中会如实保留实际记录到的轮数，不补全为假数据。

输出：round, new_posts, new_comments, new_actions, new_likes, new_shares,
      active_agents, cumulative_posts, cumulative_actions
"""
import csv
import json
import os
import sys
from collections import defaultdict


def parse(raw_path, out_csv):
    with open(raw_path, encoding="utf-8") as f:
        data = json.load(f)

    meta = data.get("_meta", {})
    timeline = ((data.get("timeline") or {}).get("timeline")) or []
    twitter_posts = data.get("posts") or []
    reddit_posts = data.get("reddit_posts") or []
    tw_comments = data.get("comments") or []
    rd_comments = data.get("reddit_comments") or []

    all_posts = list(twitter_posts) + list(reddit_posts)
    all_comments = list(tw_comments) + list(rd_comments)

    rows = []
    if timeline:
        # 主路径：以 timeline 的 round_num 作为轮次索引
        for entry in timeline:
            r = entry.get("round_num", 0)
            at = entry.get("action_types") or {}
            rows.append({
                "round": r,
                "new_posts": int(at.get("CREATE_POST", 0)),
                "new_comments": int(at.get("CREATE_COMMENT", 0)),
                "new_actions": int(entry.get("total_actions") or 0),
                "new_likes": int(at.get("LIKE_POST", 0) or at.get("LIKE", 0)),
                "new_shares": int(at.get("REPOST", 0) or at.get("SHARE", 0)),
                "active_agents": int(entry.get("active_agents_count") or 0),
                "source": "timeline",
            })
    else:
        # 降级：无 timeline 时按 created_at 均分不可靠，直接报错而非编造
        raise SystemExit(
            "导出数据缺少 timeline；MiroFish 帖子无 round 字段，"
            "无法安全还原逐轮数据，请检查 simulation/timeline 接口。"
        )

    rows.sort(key=lambda x: x["round"])

    # 帖子侧汇总（不按轮，仅作为整体规模交叉校验）
    total_likes = sum(int(p.get("num_likes") or 0) for p in all_posts)
    total_shares = sum(int(p.get("num_shares") or 0) for p in all_posts)

    cum_p = cum_a = 0
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["round", "new_posts", "new_comments", "new_actions",
                    "new_likes", "new_shares", "active_agents",
                    "cumulative_posts", "cumulative_actions", "source"])
        for r in rows:
            cum_p += r["new_posts"]
            cum_a += r["new_actions"]
            w.writerow([r["round"], r["new_posts"], r["new_comments"], r["new_actions"],
                        r["new_likes"], r["new_shares"], r["active_agents"],
                        cum_p, cum_a, r["source"]])

    agents_count = ((data.get("agent_stats") or {}).get("agents_count"))
    print(f"已写出 {out_csv}")
    print(f"  记录轮数={len(rows)}  总动作={cum_a}  累计发帖={cum_p}")
    print(f"  Agent 总数={agents_count}  帖子总数={len(all_posts)}  评论总数={len(all_comments)}")
    print(f"  [交叉校验] 帖子侧 num_likes 合计={total_likes}  num_shares 合计={total_shares}")
    print(f"  sim_id={meta.get('simulation_id')}  导出时间={meta.get('exported_at')}")
    return out_csv


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else "mirofish/results/smoke_test_20261020/raw_export.json"
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(raw), "per_round.csv")
    parse(raw, out)
