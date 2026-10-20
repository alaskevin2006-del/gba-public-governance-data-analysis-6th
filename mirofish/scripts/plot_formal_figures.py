#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
正式实验论文图（全部数据来自真实运行的 metrics_per_round.csv）

输出：
  图4-1：政府辟谣介入时点对谣言传播的影响（E1A 基线 / E2R1 / E2R4 / E2R12）
  图4-2：政府辟谣回应形态对谣言传播的影响（E1A 基线 / E2R4 公文式 / E3B 数智实证式）
  图4-4：谣言形式对传播的影响（E1A 传统文字 / E1B AIGC 高拟真图文）
  图4-5：各条件累计指标汇总条形图（含重复运行的极差）

守卫：任一图的有效条件 < 2 时拒绝出该图（不用空白/示例数据冒充成果）。
"""
import csv
import json
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "mirofish", "scripts"))
from style_config import apply_style, PALETTE  # noqa: E402

OUT = os.path.join(REPO, "deliverables", "figures")
DEFAULT_ROOT = os.path.join(REPO, "mirofish", "results", "formal_20261021")

# condition -> (标签, 颜色, 标记)
STYLE = {
    "E1A":   ("基线：无官方干预", "#595959", "o"),
    "E1B":   ("AIGC 高拟真图文谣言", "#d95f0e", "s"),
    "E2R1":  ("第1小时辟谣", "#1a9850", "^"),
    "E2R4":  ("第4小时辟谣", "#2c7fb8", "D"),
    "E2R12": ("第12小时辟谣", "#7b3294", "v"),
    "E3B":   ("第4小时·数智实证式", "#c51b7d", "P"),
}


def load(root):
    path = os.path.join(root, "summary", "per_round_long.csv")
    if not os.path.exists(path):
        raise SystemExit(f"缺少汇总数据: {path}（请先运行 analyze_formal_results.py）")
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    data = {}
    for r in rows:
        cond = r["condition"].split("_rep")[0]
        rep = r["condition"]
        # 谣言相关互动 = 谣言类内容 + 指向谣言内容的互动
        rr = int(r["content_rumor"]) + int(r["engage_rumor"])
        dd = int(r["content_debunk"]) + int(r["engage_debunk"])
        rec = {
            "round": int(r["round"]),
            "interactions": int(r["interactions"]),
            "cum_interactions": int(r["cumulative_interactions"]),
            "rumor_related": rr,
            "cum_rumor_related": int(r["cumulative_content_rumor"]) + int(r["engage_rumor"]),
            "content_rumor": int(r["content_rumor"]),
            "content_debunk": int(r["content_debunk"]),
            "debunk_related": dd,
        }
        data.setdefault(cond, {}).setdefault(rep, []).append(rec)
    return data


def series_matrix(data, cond, key, nrounds):
    """返回该条件各重复的序列矩阵 (nrep, nrounds)。"""
    reps = sorted(data.get(cond, {}).keys())
    if not reps:
        return None
    mat = []
    for rep in reps:
        rows = sorted(data[cond][rep], key=lambda x: x["round"])[:nrounds]
        mat.append([r[key] for r in rows])
    m = max(len(v) for v in mat)
    mat = [v + [v[-1] if v else 0] * (m - len(v)) for v in mat]
    return np.array(mat)


def plot_panels(root, conds, title, fname, nrounds, tag):
    data = load(root)
    present = [c for c in conds if c in data]
    missing = [c for c in conds if c not in data]
    if missing:
        print(f"[warn] 缺条件数据: {missing}")
    if len(present) < 2:
        print(f"[skip] {fname}: 有效条件仅 {len(present)} 个（需≥2），拒绝出图")
        return None

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    for c in present:
        label, color, marker = STYLE.get(c, (c, "#333333", "o"))
        mat_p = series_matrix(data, c, "rumor_related", nrounds)
        cum = np.cumsum(mat_p, axis=1)
        rounds = np.arange(1, mat_p.shape[1] + 1)
        mean_p, lo_p, hi_p = mat_p.mean(0), mat_p.min(0), mat_p.max(0)
        mean_c, lo_c, hi_c = cum.mean(0), cum.min(0), cum.max(0)
        axes[0].plot(rounds, mean_p, marker, color=color, mec="white",
                     ms=4.5, lw=1.7, label=label)
        if mat_p.shape[0] > 1:
            axes[0].fill_between(rounds, lo_p, hi_p, color=color, alpha=0.12)
        axes[1].plot(rounds, mean_c, marker, color=color, mec="white",
                     ms=4.5, lw=1.7, label=label)
        if mat_p.shape[0] > 1:
            axes[1].fill_between(rounds, lo_c, hi_c, color=color, alpha=0.12)

    for ax, sub, ylab in zip(axes, ["(a) 每轮谣言相关互动量", "(b) 累计谣言相关互动量"],
                             ["互动量（条）", "累计互动量（条）"]):
        ax.set_xlabel("模拟轮次（1 轮 = 60 模拟分钟）")
        ax.set_ylabel(ylab)
        ax.set_title(sub)
        ax.legend(fontsize=9, frameon=False)
        ax.set_xticks(np.arange(1, nrounds + 1, 2))

    n_rep = max(len(data[c]) for c in present)
    fig.suptitle(f"{title}\n（{len(present)} 个条件，每组 {n_rep} 次独立重复；探索性仿真，非现实因果效应）",
                 y=1.06, fontsize=11)
    fig.tight_layout()
    os.makedirs(OUT, exist_ok=True)
    pdf = os.path.join(OUT, f"{fname}_{tag}.pdf")
    png = os.path.join(OUT, f"{fname}_{tag}.png")
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[ok] {pdf}\n     {png}")
    return pdf


def plot_summary_bars(root, tag):
    data = load(root)
    metrics_path = os.path.join(root, "summary", "by_condition_metrics.csv")
    if not os.path.exists(metrics_path):
        print("[skip] 无按条件汇总表")
        return None
    rows = list(csv.DictReader(open(metrics_path, encoding="utf-8-sig")))
    if not rows:
        return None
    conds = [r["group"] for r in rows]
    labels = [STYLE.get(c, (c,))[0] for c in conds]
    x = np.arange(len(conds))
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.4))
    specs = [("rumor_related_actions", "谣言相关互动总量"),
             ("content_debunk", "辟谣/求证类内容量"),
             ("peak_interactions", "单轮互动峰值")]
    for ax, (key, name) in zip(axes, specs):
        means = [float(r[f"{key}_mean"]) for r in rows]
        lo = [float(r[f"{key}_min"]) for r in rows]
        hi = [float(r[f"{key}_max"]) for r in rows]
        err = np.array([[m - l, h - m] for m, l, h in zip(means, lo, hi)]).T
        ax.bar(x, means, color=[STYLE.get(c, (c, "#666"))[1] for c in conds], alpha=0.85)
        if any((h - l) > 0 for l, h in zip(lo, hi)):
            ax.errorbar(x, means, yerr=err, fmt="none", ecolor="#333", capsize=4, lw=1.2)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=8.5)
        ax.set_title(name)
        ax.set_ylabel("条数" if "interactions" not in key else "条数")
    fig.suptitle(f"各实验条件核心指标对比（误差线为 {rows[0]['n_reps']} 次重复的极差）",
                 y=1.04, fontsize=11)
    fig.tight_layout()
    pdf = os.path.join(OUT, f"图4-5_各条件核心指标对比_{tag}.pdf")
    png = os.path.join(OUT, f"图4-5_各条件核心指标对比_{tag}.png")
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[ok] {pdf}")
    return pdf


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ROOT
    tag = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(root.rstrip("/\\"))
    apply_style()
    nrounds = 16
    made = []
    made.append(plot_panels(root, ["E1A", "E2R1", "E2R4", "E2R12"],
                            "图 4-1 政府辟谣介入时点对谣言传播的影响",
                            "图4-1_辟谣介入时点对比", nrounds, tag))
    made.append(plot_panels(root, ["E1A", "E2R4", "E3B"],
                            "图 4-2 政府辟谣回应形态对谣言传播的影响",
                            "图4-2_辟谣回应形态对比", nrounds, tag))
    made.append(plot_panels(root, ["E1A", "E1B"],
                            "图 4-4 谣言形式对传播的影响（E1B 为文本代理刺激）",
                            "图4-4_谣言形式对比", nrounds, tag))
    made.append(plot_summary_bars(root, tag))
    ok = [m for m in made if m]
    print(f"\n共输出 {len(ok)} 组图表 -> {OUT}")


if __name__ == "__main__":
    main()
