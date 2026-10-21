#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
重复实验的统计摘要（描述性，不做显著性检验）

为什么不做显著性检验：
  每组有效重复只有 2-3 次，任何基于正态近似的 p 值都不诚实。
  这里改用**以重复内部的变异作为噪声尺度**的思路：
  用重复次数最多的条件（当前为 E1A）的组内极差/标准差，作为
  "本实验系统在相同设置下自身能波动多少"的经验估计；
  若某两条件均值之差小于这个噪声尺度，就应表述为
  "未能检出差异"，而不是"两者相等"或"某者更优"。

输出 mirofish/results/<tag>/summary/重复实验统计摘要.csv 与控制台表格。
"""
import csv
import json
import math
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ORDER = ["E1A", "E1B", "E2R1", "E2R4", "E2R12", "E3B"]

LABEL = {
    "E1A": "E1A 基线（文字谣言·无干预）",
    "E1B": "E1B AIGC 图文谣言（无干预）",
    "E2R1": "E2R1 第1模拟小时介入",
    "E2R4": "E2R4 第4模拟小时介入",
    "E2R12": "E2R12 第12模拟小时介入",
    "E3B": "E3B 数智实证型辟谣（第4小时）",
}

METRICS = [
    ("interactions", "自发互动总量"),
    ("rumor_related", "谣言相关互动"),
    ("debunk_related", "辟谣/求证相关互动"),
    ("content_rumor", "谣言立场内容"),
    ("engage_rumor", "指向谣言的互动"),
    ("content_debunk", "辟谣立场内容"),
    ("engage_debunk", "指向辟谣的互动"),
]

# 派生指标：谣言相关互动占自发互动总量的比例。
# 用途是排除混淆——若某组总互动量整体偏低，谣言相关的绝对值低可能只是
# "整体不活跃"，而非"结构转向辟谣"。用比例再算一遍是必要的稳健性检验。
DERIVED = [("rumor_share", "谣言相关互动占比（%）")]


def load(root):
    """返回 {cond: {metric: [values...]}}，自动跳过无效目录。"""
    out = {}
    runs = os.path.join(root, "runs")
    for name in sorted(os.listdir(runs)):
        d = os.path.join(runs, name)
        if not os.path.isdir(d):
            continue
        if re.search(r"INVALID|CRASHED|FAILED", name, re.I):
            continue
        m = re.match(r"^([A-Z0-9]+)_rep(\d+)$", name)
        if not m:
            continue
        p = os.path.join(d, "metrics_v2.json")
        if not os.path.exists(p):
            continue
        s = json.load(open(p, encoding="utf-8"))
        t = s["totals"]
        cond = m.group(1)
        slot = out.setdefault(cond, {k: [] for k, _ in METRICS + DERIVED})
        for k, _ in METRICS:
            slot[k].append(int(t.get(k, 0)))
        tot = int(t.get("interactions", 0))
        slot["rumor_share"].append(
            round(100.0 * int(t.get("rumor_related", 0)) / tot, 2) if tot else 0.0)
    return out


def stats(vals):
    n = len(vals)
    if n == 0:
        return None
    mean = sum(vals) / n
    if n > 1:
        var = sum((x - mean) ** 2 for x in vals) / (n - 1)
        sd = math.sqrt(var)
    else:
        sd = None
    return {"n": n, "mean": mean, "sd": sd, "min": min(vals),
            "max": max(vals), "range": max(vals) - min(vals), "vals": vals}


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else \
        os.path.join(REPO, "mirofish", "results", "formal_20261021")
    tag = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(root.rstrip("/\\"))
    data = load(root)
    if not data:
        print("[error] 无有效数据")
        return

    # 以重复次数最多的条件作为噪声基准
    ref = max(data, key=lambda c: len(data[c]["interactions"]))
    nref = len(data[ref]["interactions"])

    print("=" * 78)
    print(f"重复实验统计摘要   噪声基准条件 = {ref} (n={nref})")
    print("=" * 78)

    for key, name in METRICS + DERIVED:
        print(f"\n--- {name} ({key}) ---")
        print(f"{'条件':<8}{'n':<4}{'均值':>8}{'SD':>8}{'极差':>7}   各次观测值")
        rows = []
        for c in ORDER:
            if c not in data or not data[c][key]:
                continue
            st = stats(data[c][key])
            sd = f"{st['sd']:.2f}" if st["sd"] is not None else "—"
            print(f"{c:<9}{st['n']:<4}{st['mean']:>8.1f}{sd:>8}"
                  f"{st['range']:>7.2f}   {st['vals']}")
            rows.append((c, st))
        if not rows:
            continue

        ref_st = next((st for c, st in rows if c == ref), None)
        if ref_st and ref_st["sd"] is not None:
            noise = ref_st["sd"]
            noise_rng = ref_st["range"]
            print(f"  噪声尺度（{ref} 组内 SD） = {noise:.2f}；"
                  f"组内极差 = {noise_rng:.2f}")
            base = next((st for c, st in rows if c == "E1A"), None)
            if base:
                print("  相对 E1A 的差值（|Δ| / SD 倍数）：")
                for c, st in rows:
                    if c == "E1A":
                        continue
                    d = st["mean"] - base["mean"]
                    mult = f"{abs(d) / noise:.2f}σ" if noise > 0 else "—"
                    verdict = "超出噪声" if noise and abs(d) > noise else "未超出噪声"
                    print(f"    {c:<7} Δ={d:>+7.1f}  ≈{mult:<8} {verdict}")
        elif ref_st:
            print(f"  [注] {ref} 只有 1 次观测，无法估计组内变异，"
                  f"组间差异不可与上表噪声尺度比较")

    # 导出 CSV
    out_csv = os.path.join(root, "summary", "重复实验统计摘要.csv")
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["metric", "metric_label", "condition", "condition_label",
                    "n", "mean", "sd", "min", "max", "range", "observations"])
        for key, name in METRICS + DERIVED:
            for c in ORDER:
                if c not in data or not data[c][key]:
                    continue
                st = stats(data[c][key])
                w.writerow([key, name, c, LABEL.get(c, c), st["n"],
                            round(st["mean"], 3),
                            round(st["sd"], 3) if st["sd"] is not None else "",
                            st["min"], st["max"], st["range"],
                            "|".join(map(str, st["vals"]))])
    print(f"\n[ok] -> {out_csv}")


if __name__ == "__main__":
    main()
