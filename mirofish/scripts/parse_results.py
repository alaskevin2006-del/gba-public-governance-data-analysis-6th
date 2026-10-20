"""
解析 MiroFish 原始导出（raw_export.json）→ 逐轮标准 CSV
输出列：round, new_posts, new_comments, new_reposts, new_likes, cumulative_posts, cumulative_comments
注意：列名以 MiroFish 实际输出字段为准；首次真实运行后如字段不符，在此适配（勿改上游）。
"""
import json
import os
import sys
import csv
from collections import defaultdict


def parse(raw_path, out_csv):
    with open(raw_path, encoding="utf-8") as f:
        data = json.load(f)

    posts = data.get("posts") or []
    comments = data.get("comments") or []
    meta = data.get("_meta", {})

    rounds = defaultdict(lambda: {"new_posts": 0, "new_comments": 0,
                                  "new_reposts": 0, "new_likes": 0})

    for p in posts:
        r = int(p.get("round") or p.get("step") or 0)
        rounds[r]["new_posts"] += 1
        rounds[r]["new_reposts"] += int(p.get("repost_count") or 0)
        rounds[r]["new_likes"] += int(p.get("like_count") or 0)
    for c in comments:
        r = int(c.get("round") or c.get("step") or 0)
        rounds[r]["new_comments"] += 1

    if not rounds:
        # 无逐轮字段时降级：按时间序均分不可行，直接报错提示适配
        raise SystemExit("未在导出数据中找到 round/step 字段，请检查字段名并适配本脚本")

    cum_p = cum_c = 0
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["round", "new_posts", "new_comments", "new_reposts", "new_likes",
                    "cumulative_posts", "cumulative_comments"])
        for r in sorted(rounds):
            d = rounds[r]
            cum_p += d["new_posts"]
            cum_c += d["new_comments"]
            w.writerow([r, d["new_posts"], d["new_comments"], d["new_reposts"],
                        d["new_likes"], cum_p, cum_c])
    print(f"已写出 {out_csv}（{len(rounds)} 轮，来源 {meta.get('exp', '?')}）")


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else "mirofish/results/exp1_baseline/raw_export.json"
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(raw), "per_round.csv")
    parse(raw, out)
