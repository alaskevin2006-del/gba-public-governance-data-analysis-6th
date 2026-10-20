"""
图 5-1：涉灾 AIGC 虚假信息数智治理协同机制图
依据：docs/01 实施方案任务四（事前沙盒打标 / 事中实证对冲 / 事后跨域联动）
说明：仅呈现实施方案已定机制框架，不新增团队未采纳的政策结论；
      待主笔第五章要点确认后可在此基础上微调措辞。
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
OUT_PDF = f"{REPO}/deliverables/figures/图5-1_数智治理协同机制图.pdf"
OUT_PNG = f"{REPO}/deliverables/figures/图5-1_数智治理协同机制图.png"

C_PHASE = ["#fdf3e7", "#e8f0fa", "#eaf5ec"]
C_EDGE = ["#d95f0e", "#2c7fb8", "#1a9850"]


def box(ax, x, y, w, h, text, fc, ec, fs=9.5, weight="normal"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01",
                                fc=fc, ec=ec, lw=1.4))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, weight=weight, linespacing=1.5)


def arrow(ax, p1, p2, color="#555555", lw=1.6):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=15,
                                 color=color, lw=lw, shrinkA=2, shrinkB=2))


def main():
    apply_style()
    fig, ax = plt.subplots(figsize=(14, 7.8))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    # ── 三阶段主框 ──
    phases = [
        (0.03, "事前：预警沙盒打标", [
            "平台 AIGC 识别与打标拦截",
            "灾害高敏期'先标源、限流审、后放行'",
            "涉灾关键词与生成特征库备案",
        ]),
        (0.37, "事中：黄金窗口以数治假", [
            "1–2 小时政务响应标准（实验二）",
            "安置点监控 + 商超保供 + 排涝调度\n实时数据对冲（表 2-2 弹药库）",
            "AI 造假特征拆解随通报同步发布",
        ]),
        (0.71, "事后：跨域联动疏导", [
            "网信-应急-商务-平台闭环联动",
            "依法处置造谣者并公开典型案例",
            "分圈层疏导（长辈/青年差异化）",
        ]),
    ]
    for i, (x, title, items) in enumerate(phases):
        box(ax, x, 0.70, 0.26, 0.13, title, C_PHASE[i], C_EDGE[i], fs=12, weight="bold")
        for j, it in enumerate(items):
            box(ax, x, 0.52 - j * 0.145, 0.26, 0.115, it, "white", C_EDGE[i], fs=9)
            arrow(ax, (x + 0.13, 0.70), (x + 0.13, 0.52 - j * 0.145 + 0.115), color=C_EDGE[i], lw=1.1)

    # 阶段间箭头
    arrow(ax, (0.29, 0.765), (0.37, 0.765), color="#333333", lw=2.2)
    arrow(ax, (0.63, 0.765), (0.71, 0.765), color="#333333", lw=2.2)

    # ── 底部数据底座 ──
    box(ax, 0.03, 0.03, 0.94, 0.10,
        "数据底座：官方辟谣库（定性基准） × 政务客观数据（事实弹药） × 舆情反馈（效果回流）\n"
        "仿真验证：MiroFish 反事实推演为机制设计提供'介入时点'与'回应形态'的探索性证据",
        "#f5f5f5", "#888888", fs=9.5)
    for x in (0.16, 0.50, 0.84):
        arrow(ax, (x, 0.13), (x, 0.20), color="#888888", lw=1.2)

    ax.text(0.5, 0.965, "图 5-1  涉灾 AIGC 虚假信息“事前-事中-事后”数智治理协同机制",
            ha="center", va="top", fontsize=13, weight="bold")
    ax.text(0.5, 0.885, "依据：实施方案任务四治理机制框架；实验二/三的反事实证据用于支撑事中窗口与回应形态选择",
            ha="center", fontsize=8.5, color="#666666")

    fig.tight_layout()
    fig.savefig(OUT_PDF, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
    print(f"图 5-1 已导出：{OUT_PDF}")


if __name__ == "__main__":
    main()
