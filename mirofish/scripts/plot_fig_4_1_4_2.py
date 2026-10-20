"""
图 4-1 / 图 4-2 绘制脚本（读取 compute_metrics 产出的 metrics_summary.json + 各实验 per_round.csv）
图 4-1：实验二——不同辟谣介入时点的传播曲线对比（1h/4h/12h vs 无干预）
图 4-2：实验三——公文辟谣 vs 数智实证辟谣的传播曲线对比
⚠️ 只接受真实仿真数据。数据文件不存在时直接退出，绝不生成示例曲线。
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from style_config import FIG_STYLE, apply_style

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS = os.path.join(REPO, "mirofish", "results")
OUT = os.path.join(REPO, "deliverables", "figures")


def load_series(exp_dir):
    p = os.path.join(RESULTS, exp_dir, "per_round.csv")
    if not os.path.exists(p):
        sys.exit(f"缺少真实数据 {p} —— 先运行仿真，禁止用假数据绘图")
    import csv
    rows = list(csv.DictReader(open(p, encoding="utf-8-sig")))
    return [int(r["new_posts"]) + int(r["new_comments"]) for r in rows], \
           [int(r["cumulative_posts"]) + int(r["cumulative_comments"]) for r in rows]


def plot_fig_4_1():
    """实验二：介入时点对比"""
    apply_style()
    groups = [
        ("exp1_baseline", "无干预（基准）", "#8c8c8c"),
        ("exp2_t1h", "辟谣 @1h（第1轮）", "#d62728"),
        ("exp2_t4h", "辟谣 @4h（第2轮）", "#ff7f0e"),
        ("exp2_t12h", "辟谣 @12h（第6轮）", "#1f77b4"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for name, label, color in groups:
        try:
            per, cum = load_series(name)
        except SystemExit:
            print(f"跳过缺失组: {name}")
            continue
        rounds = range(1, len(per) + 1)
        axes[0].plot(rounds, per, "o-", color=color, label=label, lw=1.8, ms=4)
        axes[1].plot(rounds, cum, "o-", color=color, label=label, lw=1.8, ms=4)
    for ax, title in zip(axes, ["(a) 每轮新增传播量", "(b) 累计传播规模"]):
        ax.set_xlabel("模拟轮次（1 轮 ≈ 2 小时）")
        ax.set_ylabel("帖子 + 评论数")
        ax.set_title(title)
        ax.legend(fontsize=9)
        ax.grid(alpha=0.3)
    fig.suptitle("图 4-1 政府辟谣介入时点对谣言传播的影响（反事实推演）", y=1.02)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"图4-1_辟谣时点对比.{ext}"), dpi=300, bbox_inches="tight")
    print("图 4-1 已导出")


def plot_fig_4_2():
    """实验三：辟谣形态对比"""
    apply_style()
    groups = [
        ("exp1_baseline", "无干预（基准）", "#8c8c8c"),
        ("exp3_form_A", "公文辟谣（情景A）", "#1f77b4"),
        ("exp3_form_B", "数智实证辟谣（情景B）", "#2ca02c"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for name, label, color in groups:
        try:
            per, cum = load_series(name)
        except SystemExit:
            print(f"跳过缺失组: {name}")
            continue
        rounds = range(1, len(per) + 1)
        axes[0].plot(rounds, per, "o-", color=color, label=label, lw=1.8, ms=4)
        axes[1].plot(rounds, cum, "o-", color=color, label=label, lw=1.8, ms=4)
    for ax, title in zip(axes, ["(a) 每轮新增传播量", "(b) 累计传播规模"]):
        ax.set_xlabel("模拟轮次（1 轮 ≈ 2 小时）")
        ax.set_ylabel("帖子 + 评论数")
        ax.set_title(title)
        ax.legend(fontsize=9)
        ax.grid(alpha=0.3)
    fig.suptitle("图 4-2 政府辟谣形态对谣言传播的影响（反事实推演）", y=1.02)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"图4-2_辟谣形态对比.{ext}"), dpi=300, bbox_inches="tight")
    print("图 4-2 已导出")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "1"):
        plot_fig_4_1()
    if which in ("all", "2"):
        plot_fig_4_2()
