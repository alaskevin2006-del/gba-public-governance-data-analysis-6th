"""
从逐轮 CSV 计算传播指标（实验一/二/三通用）
指标定义（全部基于可观测的帖子/评论行为，不含不可测的"恐慌率"）：
  - 传播峰值 peak        = max(new_posts + new_comments)
  - 达峰轮次 peak_round
  - 达峰时间(模拟小时)    = peak_round * minutes_per_round / 60
  - 累计规模 total       = 累计 posts + comments
  - 消退速度             = 从峰值降到峰值 20% 所用轮数
  - 半衰期               = 从峰值降到 50% 所用轮数

【2026-10-20 真实运行校准】
早期版本写死「1 轮 ≈ 2 小时」，与 MiroFish 实际不符。
实跑 sim_5379ef9a11b5 读到的真实配置为 `time_config.minutes_per_round = 60`，
即 **1 轮 = 1 模拟小时**。该值由 LLM 在 prepare 阶段按事件动态生成，
因此不再写死，改为由 --minutes-per-round 指定，默认 60（实测值）。
每次正式实验都应以该实验 `simulation_config.json` 中的真实值为准。
"""
import csv
import json
import sys


def metrics(per_round_csv, minutes_per_round=60):
    rows = list(csv.DictReader(open(per_round_csv, encoding="utf-8-sig")))
    series = [int(r["new_posts"]) + int(r["new_comments"]) for r in rows]
    if not series:
        raise SystemExit("空数据")
    peak = max(series)
    peak_round = series.index(peak) + 1

    # 轮 → 模拟小时换算：以该实验 simulation_config.json 的 time_config 为准
    hours_per_round = minutes_per_round / 60.0

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
        "peak_time_sim_hours": peak_round * hours_per_round,
        "minutes_per_round": minutes_per_round,
        "half_life_rounds": rounds_to_fall(0.5),
        "decay_to_20pct_rounds": rounds_to_fall(0.2),
        "series": series,
    }


if __name__ == "__main__":
    # 可选：--minutes-per-round N（默认 60，来自实测 simulation_config.json 的 time_config）
    mpr = 60
    args = []
    it = iter(sys.argv[1:])
    for a in it:
        if a == "--minutes-per-round":
            mpr = int(next(it))
        else:
            args.append(a)

    if not args:
        raise SystemExit(
            "用法: python compute_metrics.py [--minutes-per-round 60] "
            "exp1/per_round.csv [exp2/per_round.csv ...]"
        )
    out = {}
    for path in args:
        name = path.rstrip("/\\").replace("\\", "/").split("/")[-2] if "/" in path.replace("\\", "/") else path
        out[name] = metrics(path, minutes_per_round=mpr)
        m = out[name]
        print(f"{name}: 轮数={m['rounds']} 峰值={m['peak']}(第{m['peak_round']}轮≈{m['peak_time_sim_hours']}h) "
              f"总量={m['total_activity']} 半衰期={m['half_life_rounds']}轮 "
              f"[1轮={mpr}分钟]")
    if len(sys.argv) > 2:
        with open("metrics_summary.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print("已写出 metrics_summary.json")
