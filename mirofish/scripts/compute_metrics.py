"""
从逐轮 CSV 计算传播指标（实验一/二/三通用）
指标定义（全部基于可观测的帖子/评论行为，不含不可测的"恐慌率"）：
  - 传播峰值 peak        = max(new_posts + new_comments)
  - 达峰轮次 peak_round
  - 达峰时间(模拟小时)    = peak_round * 2（1 轮 ≈ 2 小时，时间压缩映射）
  - 累计规模 total       = 累计 posts + comments
  - 消退速度             = 从峰值降到峰值 20% 所用轮数
  - 半衰期               = 从峰值降到 50% 所用轮数
"""
import csv
import json
import sys


def metrics(per_round_csv):
    rows = list(csv.DictReader(open(per_round_csv, encoding="utf-8-sig")))
    series = [int(r["new_posts"]) + int(r["new_comments"]) for r in rows]
    if not series:
        raise SystemExit("空数据")
    peak = max(series)
    peak_round = series.index(peak) + 1

    def rounds_to_fall(frac):
        for i in range(peak_round - 1, len(series)):
            if series[i] <= peak * frac:
                return i + 1 - peak_round
        return None

    return {
        "rounds": len(series),
        "total_activity": sum(series),
        "peak": peak,
        "peak_round": peak_round,
        "peak_time_sim_hours": peak_round * 2,
        "half_life_rounds": rounds_to_fall(0.5),
        "decay_to_20pct_rounds": rounds_to_fall(0.2),
        "series": series,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("用法: python compute_metrics.py exp1/per_round.csv [exp2/per_round.csv ...]")
    out = {}
    for path in sys.argv[1:]:
        name = path.rstrip("/\\").split("/")[-2] if "/" in path else path
        out[name] = metrics(path)
        m = out[name]
        print(f"{name}: 轮数={m['rounds']} 峰值={m['peak']}(第{m['peak_round']}轮≈{m['peak_time_sim_hours']}h) "
              f"总量={m['total_activity']} 半衰期={m['half_life_rounds']}轮")
    if len(sys.argv) > 2:
        with open("metrics_summary.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print("已写出 metrics_summary.json")
