#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A/B 治理对照图：每轮互动量对照 + 累计互动量对照

数据源：各组 per_round_actions.csv（由 parse_actions.py 从真实 actions.jsonl 生成）
守卫：有效组 < 2 时拒绝出图，避免产出空白/无对照的假成果。
"""
import csv
import os
import sys

import matplotlib.pyplot as plt

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "mirofish", "scripts"))
sys.path.insert(0, os.path.join(REPO, "scripts", "figures"))
from style_config import apply_style  # noqa: E402

OUT = os.path.join(REPO, "deliverables", "figures")

GROUPS = [
    ("A", "A组：无官方干预（基线）", "#8c8c8c", "o"),
    ("B", "B组：早期官方辟谣", "#d62728", "s"),
]


def load(exp_root: str):
    series = {}
    for key, label, color, marker in GROUPS:
        p = os.path.join(exp_root, key, "per_round_actions.csv")
        if not os.path.exists(p):
            print(f"跳过缺失组 {key}: {p}")
            continue
        rows = list(csv.DictReader(open(p, encoding="utf-8-sig")))
        if not rows:
            print(f"跳过空数据组 {key}")
            continue
        series[key] = {
            "label": label, "color": color, "marker": marker,
            "rounds": [int(r["round"]) for r in rows],
            "interactions": [int(r["interactions"]) for r in rows],
            "cumulative": [int(r["cumulative_interactions"]) for r in rows],
            "posts": [int(r["posts"]) for r in rows],
            "comments": [int(r["comments"]) for r in rows],
            "likes": [int(r["likes"]) for r in rows],
            "agents": [int(r["active_agents"]) for r in rows],
        }
    return series


def main():
    exp_root = sys.argv[1] if len(sys.argv) > 1 else None
    if not exp_root:
        raise SystemExit("用法: python plot_ab_comparison.py <results/exp_ab_xxx>")
    series = load(exp_root)
    if len(series) < 2:
        raise SystemExit(f"有效组仅 {len(series)} 组（需 ≥2），拒绝出图")

    tag = os.path.basename(exp_root.rstrip("/\\"))
    apply_style()

    # --- 图1：每轮互动量 ---
    fig, ax = plt.subplots(figsize=(9, 5))
    for key, d in series.items():
        ax.plot(d["rounds"], d["interactions"], f'-{d["marker"]}',
                color=d["color"], label=d["label"], lw=2, ms=6)
    ax.set_xlabel("模拟轮次（每轮 = 60 分钟，据本次 time_config.minutes_per_round）")
    ax.set_ylabel("每轮互动量（发帖 + 评论 + 点赞）")
    ax.set_title("图 1　A/B 两组每轮互动量对照（真实仿真输出）")
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"图_AB1_每轮互动量对照_{tag}.{ext}"),
                    dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("图1 已导出")

    # --- 图2：累计互动量 ---
    fig, ax = plt.subplots(figsize=(9, 5))
    for key, d in series.items():
        ax.plot(d["rounds"], d["cumulative"], f'-{d["marker"]}',
                color=d["color"], label=d["label"], lw=2, ms=6)
    ax.set_xlabel("模拟轮次（每轮 = 60 分钟）")
    ax.set_ylabel("累计互动量")
    ax.set_title("图 2　A/B 两组累计互动量对照（真实仿真输出）")
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"图_AB2_累计互动量对照_{tag}.{ext}"),
                    dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("图2 已导出")

    # --- 汇总表 ---
    rows = []
    for key, d in series.items():
        rows.append({
            "组": d["label"],
            "轮数": len(d["rounds"]),
            "总互动量": sum(d["interactions"]),
            "发帖": sum(d["posts"]),
            "评论": sum(d["comments"]),
            "点赞": sum(d["likes"]),
            "峰值互动量": max(d["interactions"]),
            "峰值轮次": d["rounds"][d["interactions"].index(max(d["interactions"]))],
            "最大单轮活跃Agent": max(d["agents"]),
        })
    out_csv = os.path.join(exp_root, "ab_comparison_summary.csv")
    with open(out_csv, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("汇总表:", out_csv)
    for r in rows:
        print("  ", r)


if __name__ == "__main__":
    main()
