"""
图 4-3：多智能体小世界传播网络拓扑机制图（NetworkX）
说明：本图为**机制示意图**——基于 Watts-Strogatz 小世界模型生成拓扑，
节点按 Seed §7 七类画像配额着色，红色边为辟谣阻断边。
正式仿真网络导出后应以此脚本为模板用真实邻接表重绘（需 API Key，当前阻塞）。
"""
import os
import sys
import numpy as np
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mirofish", "scripts"))
from style_config import apply_style

REPO = "C:/Users/Kevin/Desktop/gba-public-governance-data-analysis-6th"
OUT_PDF = f"{REPO}/deliverables/figures/图4-3_多智能体传播网络拓扑机制图.pdf"
OUT_PNG = f"{REPO}/deliverables/figures/图4-3_多智能体传播网络拓扑机制图.png"

# 七类画像（与 agent_profiles.json 一致）
CLASSES = [
    ("社区长辈", 0.20, "#f4a259"),
    ("青年学生", 0.25, "#5b8e7d"),
    ("自媒体造谣者", 0.05, "#b2182b"),
    ("转发型营销号", 0.08, "#d95f0e"),
    ("辟谣意见领袖", 0.10, "#2c7fb8"),
    ("政务发布账号", 0.07, "#1a9850"),
    ("一线亲历者", 0.25, "#8c8c8c"),
]


def main():
    apply_style()
    rng = np.random.default_rng(42)  # 固定种子保证可复现
    n = 100
    G = nx.watts_strogatz_graph(n, k=6, p=0.08, seed=42)

    # 按配额分配画像
    counts = [int(round(s * n)) for _, s, _ in CLASSES]
    counts[-1] += n - sum(counts)
    node_class = []
    for i, c in enumerate(counts):
        node_class += [i] * c
    rng.shuffle(node_class)

    colors = [CLASSES[c][2] for c in node_class]
    # 造谣者与营销号放大显示
    sizes = [260 if CLASSES[c][0] in ("自媒体造谣者", "政务发布账号") else
             (140 if CLASSES[c][0] in ("转发型营销号", "辟谣意见领袖") else 55)
             for c in node_class]

    pos = nx.spring_layout(G, seed=42, k=0.35)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6.8))

    # (a) 谣言扩散期
    ax = axes[0]
    nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.18, width=0.7, edge_color="#666666")
    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=colors, node_size=sizes,
                           linewidths=0.6, edgecolors="white")
    ax.set_title("(a) 谣言扩散期：营销号跨圈层桥接放大传播", fontsize=11.5)
    ax.axis("off")

    # (b) 辟谣阻断期：政务/辟谣KOL 的边标红（阻断边）
    ax = axes[1]
    blocked = []
    gov_nodes = [i for i, c in enumerate(node_class) if CLASSES[c][0] in ("政务发布账号", "辟谣意见领袖")]
    for u in gov_nodes:
        for v in G.neighbors(u):
            blocked.append((u, v) if u < v else (v, u))
    blocked = list(dict.fromkeys(blocked))
    normal = [e for e in G.edges() if e not in blocked]
    nx.draw_networkx_edges(G, pos, edgelist=normal, ax=ax, alpha=0.15, width=0.7, edge_color="#666666")
    nx.draw_networkx_edges(G, pos, edgelist=blocked, ax=ax, alpha=0.75, width=1.6, edge_color="#d62728")
    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=colors, node_size=sizes,
                           linewidths=0.6, edgecolors="white")
    ax.set_title("(b) 辟谣对冲期：政务/辟谣KOL 注入客观数据（红边=对冲链路）", fontsize=11.5)
    ax.axis("off")

    # 图例
    handles = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=c,
                          markersize=9, label=l) for l, _, c in CLASSES]
    fig.legend(handles=handles, loc="lower center", ncol=7, frameon=False, fontsize=9.5,
               bbox_to_anchor=(0.5, -0.01))
    fig.suptitle("图 4-3  多智能体传播网络拓扑机制图（机制示意图，Watts–Strogatz 小世界 n=100, k=6, p=0.08）",
                 fontsize=12.5, y=1.0)
    fig.text(0.5, 0.065, "注：拓扑为示意模型，非真实仿真导出；正式仿真网络经 MiroFish/OASIS 导出邻接表后按同模板重绘",
             ha="center", fontsize=8.5, color="#666666")
    fig.tight_layout(rect=[0, 0.05, 1, 0.97])
    fig.savefig(OUT_PDF, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
    print(f"图 4-3 已导出：{OUT_PDF}")


if __name__ == "__main__":
    main()
