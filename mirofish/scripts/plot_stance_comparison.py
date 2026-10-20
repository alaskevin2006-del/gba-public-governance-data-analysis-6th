#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""图3：内容立场对比（谣言放大 vs 辟谣/求证）——本轮实验的核心结论图

用各组 content_stance.csv 的累计值绘制分组柱状图。
"""
import csv
import json
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "scripts", "figures"))
from style_config import apply_style  # noqa: E402

OUT = os.path.join(REPO, "deliverables", "figures")
GROUPS = [("A", "A组：无官方干预（基线）"), ("B", "B组：早期官方辟谣")]


def load(exp_root):
    data = {}
    for key, label in GROUPS:
        p = os.path.join(exp_root, key, "content_stance_summary.json")
        if not os.path.exists(p):
            print(f"跳过缺失组 {key}")
            continue
        s = json.load(open(p, encoding="utf-8"))
        data[key] = {"label": label, "rumor": s["rumor_total"],
                     "debunk": s["debunk_total"], "neutral": s["neutral_total"]}
    return data


def main():
    exp_root = sys.argv[1] if len(sys.argv) > 1 else None
    if not exp_root:
        raise SystemExit("用法: python plot_stance_comparison.py <results/exp_ab_xxx>")
    data = load(exp_root)
    if len(data) < 2:
        raise SystemExit("有效组 < 2，拒绝出图")

    tag = os.path.basename(exp_root.rstrip("/\\"))
    apply_style()

    labels = [data[g]["label"] for g in data]
    rumor = [data[g]["rumor"] for g in data]
    debunk = [data[g]["debunk"] for g in data]
    neutral = [data[g]["neutral"] for g in data]

    x = np.arange(len(labels))
    w = 0.27
    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.bar(x - w, rumor, w, label="谣言放大类", color="#d62728")
    ax.bar(x, debunk, w, label="辟谣/求证类", color="#1f77b4")
    ax.bar(x + w, neutral, w, label="中性/其他", color="#8c8c8c")
    for i in range(len(labels)):
        ax.text(x[i] - w, rumor[i], str(rumor[i]), ha="center", va="bottom", fontsize=10)
        ax.text(x[i], debunk[i], str(debunk[i]), ha="center", va="bottom", fontsize=10)
        ax.text(x[i] + w, neutral[i], str(neutral[i]), ha="center", va="bottom", fontsize=10)
    ax.set_ylabel("内容型动作数量（发帖 + 评论）")
    ax.set_title("图 3　内容立场对比：早期官方辟谣对谣言放大类内容的影响（关键词启发式）")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.legend(fontsize=10)
    ax.grid(axis="y", alpha=0.3)
    # 标注谣言类的相对变化
    if len(rumor) == 2 and rumor[0]:
        pct = (rumor[1] - rumor[0]) / rumor[0] * 100
        ax.annotate(f"谣言类 {rumor[0]}→{rumor[1]}（{pct:+.0f}%）",
                    xy=(0.5, max(debunk) * 0.9), xycoords=("axes fraction", "data"),
                    ha="center", fontsize=10, color="#d62728")
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"图_AB3_内容立场对比_{tag}.{ext}"),
                    dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("图3 已导出")


if __name__ == "__main__":
    main()
