"""
图 1-1：研究技术路线图（矢量 PDF + 300DPI PNG）
结构：多源数据采集与清洗 → 文本实证挖掘 → 多智能体反事实推演 → 数智协同治理策略
"""
import os
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mirofish", "scripts"))
from style_config import apply_style

REPO = "C:/Users/Kevin/Desktop/gba-public-governance-data-analysis-6th"
OUT_PDF = f"{REPO}/deliverables/figures/图1-1_研究技术路线图.pdf"
OUT_PNG = f"{REPO}/deliverables/figures/图1-1_研究技术路线图.png"

C_MAIN = "#e8f0fa"   # 主流程
C_SUB = "#f5f5f5"    # 子节点
C_EDGE = "#2c7fb8"


def box(ax, x, y, w, h, text, fc=C_MAIN, fs=10, weight="normal", ec="#2c7fb8"):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012",
                       fc=fc, ec=ec, lw=1.4)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, weight=weight, linespacing=1.5)
    return (x, y, w, h)


def arrow(ax, p1, p2, label=None, color=C_EDGE):
    a = FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=16,
                        color=color, lw=1.6, shrinkA=2, shrinkB=2)
    ax.add_patch(a)
    if label:
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        ax.text(mx + 0.008, my, label, fontsize=8.5, color=color, ha="left", va="center")


def main():
    apply_style()
    fig, ax = plt.subplots(figsize=(13.5, 8.2))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # ── 第一层：数据采集 ──
    box(ax, 0.02, 0.72, 0.20, 0.22, "多源数据采集与清洗", weight="bold", fs=11)
    box(ax, 0.02, 0.55, 0.20, 0.11, "平台一：官方辟谣库\n5 条通报（定性/手法/处罚）", fc=C_SUB, fs=9)
    box(ax, 0.02, 0.40, 0.20, 0.11, "平台二：微博舆情\n18 靶标博文 + 146 清洗评论", fc=C_SUB, fs=9)
    box(ax, 0.02, 0.25, 0.20, 0.11, "平台三：政务客观数据\n35 项（排涝/保供/安置）", fc=C_SUB, fs=9)

    # ── 第二层：实证挖掘 ──
    box(ax, 0.28, 0.72, 0.20, 0.22, "文本实证挖掘", weight="bold", fs=11)
    box(ax, 0.28, 0.55, 0.20, 0.11, "SnowNLP 情感时序\n+ LDA 三主题聚类", fc=C_SUB, fs=9)
    box(ax, 0.28, 0.40, 0.20, 0.11, "33 起案例库编码\n（场景 × 手法交叉）", fc=C_SUB, fs=9)
    box(ax, 0.28, 0.25, 0.20, 0.11, "谣言话术结构化\n10 类样本（R1–R10）", fc=C_SUB, fs=9)

    # ── 第三层：反事实推演 ──
    box(ax, 0.54, 0.72, 0.20, 0.22, "MiroFish 多智能体\n反事实推演", weight="bold", fs=11)
    box(ax, 0.54, 0.55, 0.20, 0.11, "种子材料 → GraphRAG\n→ 7 类 Agent 画像生成", fc=C_SUB, fs=9)
    box(ax, 0.54, 0.40, 0.20, 0.11, "实验一：无干预基准\n实验二：介入时点 1/4/12h", fc=C_SUB, fs=9)
    box(ax, 0.54, 0.25, 0.20, 0.11, "实验三：辟谣形态\n公文 vs 数智实证", fc=C_SUB, fs=9)

    # ── 第四层：治理策略 ──
    box(ax, 0.80, 0.72, 0.18, 0.22, "数智协同\n治理策略分析", weight="bold", fs=11)
    box(ax, 0.80, 0.55, 0.18, 0.11, "黄金窗口识别\n（1–2h 介入效应）", fc=C_SUB, fs=9)
    box(ax, 0.80, 0.40, 0.18, 0.11, "以数治假：客观数据\n对冲虚假险情", fc=C_SUB, fs=9)
    box(ax, 0.80, 0.25, 0.18, 0.11, "事前-事中-事后\n协同机制设计", fc=C_SUB, fs=9)

    # ── 主箭头 ──
    arrow(ax, (0.22, 0.83), (0.28, 0.83))
    arrow(ax, (0.48, 0.83), (0.54, 0.83))
    arrow(ax, (0.74, 0.83), (0.80, 0.83))
    # 子层汇聚箭头
    for x_from, x_to, ys in [(0.22, 0.28, [0.605, 0.455, 0.305]),
                             (0.48, 0.54, [0.605, 0.455, 0.305]),
                             (0.74, 0.80, [0.605, 0.455, 0.305])]:
        for y in ys:
            arrow(ax, (x_from, y), (x_to, y), color="#9db8d2")

    # ── 底部验证回路 ──
    box(ax, 0.28, 0.06, 0.46, 0.10,
        "趋势对照验证：真实辟谣帖评论时序（51 小时点）↔ 仿真传播曲线（仅整体趋势可比）",
        fc="#fdf3e7", fs=9.5, ec="#d95f0e")
    arrow(ax, (0.54, 0.25), (0.54, 0.17), color="#d95f0e")
    ax.text(0.558, 0.205, "验证反馈", fontsize=8.5, color="#d95f0e")

    ax.text(0.5, 0.985, "图 1-1  极端气象灾害 AIGC 虚假信息扩散机理与政务治理回应研究 · 技术路线",
            ha="center", va="top", fontsize=13, weight="bold")
    ax.text(0.5, 0.012, "注：仿真结果为探索性反事实推演；真实数据局限（评论量 7.3% 达成、辟谣帖采样偏斜）已在报告中如实披露",
            ha="center", fontsize=8, color="#666666")

    fig.tight_layout()
    fig.savefig(OUT_PDF, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
    print(f"图 1-1 已导出：{OUT_PDF}")


if __name__ == "__main__":
    main()
