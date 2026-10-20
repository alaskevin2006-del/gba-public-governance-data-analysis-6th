"""图表统一风格（全部 lkx 图表共用）"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 中文字体：Windows 优先 Microsoft YaHei，退化 SimHei
for f in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC"):
    if any(x.name == f for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = [f, "DejaVu Sans"]
        break
plt.rcParams["axes.unicode_minus"] = False

FIG_STYLE = {
    "figsize": (10, 6),
    "dpi": 300,
    "font_size": 11,
    "title_size": 13,
    "grid_alpha": 0.3,
}

# 论文用色板（避免默认高饱和）
PALETTE = ["#2c7fb8", "#d95f0e", "#31a354", "#8c8c8c", "#b2182b"]


def apply_style():
    plt.rcParams.update({
        "figure.dpi": 120,
        "font.size": FIG_STYLE["font_size"],
        "axes.titlesize": FIG_STYLE["title_size"],
        "axes.grid": True,
        "grid.alpha": FIG_STYLE["grid_alpha"],
        "axes.spines.top": False,
        "axes.spines.right": False,
    })
