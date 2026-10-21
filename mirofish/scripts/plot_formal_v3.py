#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
正式实验论文图 v3（数据源：各运行的 metrics_per_round_v2.csv）

相对上一版的改动：
  * 数据源换成 analyze_formal_v2.py 的产出（已剔除初始帖重复计数、round 0 不计入自发互动、
    内容立场改用 content_classifier_v2）。
  * 自动跳过标注为无效的运行目录（含 INVALID / CRASHED 字样）。
  * 每次都在图注里写明"每组重复次数"，单次重复时不画虚假的误差带。
  * 保留 required 守卫：构成对照关系的关键条件缺失时拒绝出图，不用空图充数。

输出：图 4-1 / 4-2 / 4-4 / 4-5
"""
import csv
import os
import re
import sys

import matplotlib.pyplot as plt
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "mirofish", "scripts"))
from style_config import apply_style  # noqa: E402

OUT = os.path.join(REPO, "deliverables", "figures")
DEFAULT_ROOT = os.path.join(REPO, "mirofish", "results", "formal_20261021")

INJ_ROUND = {"E2R1": 1, "E2R4": 4, "E2R12": 12, "E3B": 4}

STYLE = {
    "E1A":   ("基线：无官方干预（文字谣言）", "#595959", "o"),
    "E1B":   ("AIGC 高拟真图文谣言（无干预）", "#d95f0e", "s"),
    "E2R1":  ("第 1 模拟小时辟谣（公文式）", "#1a9850", "^"),
    "E2R4":  ("第 4 模拟小时辟谣（公文式）", "#2c7fb8", "D"),
    "E2R12": ("第 12 模拟小时辟谣（公文式）", "#7b3294", "v"),
    "E3B":   ("第 4 模拟小时辟谣（数智实证式）", "#c51b7d", "P"),
}


def discover(root):
    """返回 {cond: [ (rep_name, [row...]) ]}，自动排除无效运行目录。"""
    data, skipped = {}, []
    runs = os.path.join(root, "runs")
    for name in sorted(os.listdir(runs)):
        d = os.path.join(runs, name)
        if not os.path.isdir(d):
            continue
        if re.search(r"INVALID|CRASHED|FAILED", name, re.I):
            skipped.append(name)
            continue
        m = re.match(r"^([A-Z0-9]+)_rep(\d+)$", name)
        if not m:
            continue
        cond, rep = m.group(1), int(m.group(2))
        p = os.path.join(d, "metrics_per_round_v2.csv")
        if not os.path.exists(p):
            skipped.append(name + "(无v2指标)")
            continue
        rows = list(csv.DictReader(open(p, encoding="utf-8-sig")))
        rows = [r for r in rows if int(r["round"]) >= 1]
        if len(rows) < 8:
            skipped.append(name + "(轮次不足)")
            continue
        data.setdefault(cond, []).append((name, rows))
    if skipped:
        print(f"[info] 已跳过无效/不完整运行: {skipped}")
    return data


def matrix(data, cond, key, nrounds):
    if cond not in data:
        return None
    mat = []
    for _, rows in data[cond]:
        vals = [int(r[key]) for r in sorted(rows, key=lambda x: int(x["round"]))[:nrounds]]
        if len(vals) < nrounds:
            vals += [0] * (nrounds - len(vals))
        mat.append(vals)
    return np.array(mat)


def plot_panels(root, data, conds, title, fname, nrounds, tag, required=None):
    required = required or []
    missing_req = [c for c in required if c not in data]
    present = [c for c in conds if c in data]
    missing = [c for c in conds if c not in data]
    if missing:
        print(f"[warn] {fname}: 缺条件 {missing}")
    if missing_req:
        print(f"[skip] {fname}: 缺关键条件 {missing_req}，拒绝出图")
        return None
    if len(present) < 2:
        print(f"[skip] {fname}: 有效条件 {len(present)} < 2，拒绝出图")
        return None

    fig, axes = plt.subplots(1, 2, figsize=(12.4, 4.8))
    for c in present:
        label, color, marker = STYLE.get(c, (c, "#333333", "o"))
        mat = matrix(data, c, "rumor_related", nrounds)
        cum = np.cumsum(mat, axis=1)
        rounds = np.arange(1, mat.shape[1] + 1)
        for ax, series in ((axes[0], mat), (axes[1], cum)):
            mean = series.mean(0)
            ax.plot(rounds, mean, marker, color=color, mec="white", ms=4.5,
                    lw=1.8, label=label)
            if series.shape[0] > 1:
                ax.fill_between(rounds, series.min(0), series.max(0),
                                color=color, alpha=0.15)

    for ax, sub, ylab in zip(axes,
                             ["(a) 每轮谣言相关互动量", "(b) 累计谣言相关互动量"],
                             ["互动量（条 / 轮）", "累计互动量（条）"]):
        ax.set_xlabel("模拟轮次（1 轮 = 60 模拟分钟 = 第 k 模拟小时）")
        ax.set_ylabel(ylab)
        ax.set_title(sub)
        ax.set_xticks(np.arange(1, nrounds + 1, 2))
        ax.legend(fontsize=8.6, frameon=False)

    ymax = axes[0].get_ylim()[1]
    for c in present:
        r = INJ_ROUND.get(c)
        if r:
            col = STYLE.get(c, (c, "#999"))[1]
            for ax in axes:
                ax.axvline(r, color=col, ls="--", alpha=0.4, lw=1.1)
            axes[0].text(r + 0.12, ymax * 0.93, f"第{r}小时\n介入",
                         color=col, fontsize=7.6, va="top")

    n_rep = max(len(data[c]) for c in present)
    rep_note = f"每组 {n_rep} 次独立重复（阴影为极差）" if n_rep > 1 else "每组 1 次运行，无误差估计"
    miss_note = f"；缺失：{'、'.join(missing)}" if missing else ""
    fig.suptitle(f"{title}\n{rep_note}{miss_note}；探索性反事实仿真，"
                 f"模拟小时不等于经校准的现实小时", y=1.07, fontsize=10.6)
    fig.tight_layout()
    os.makedirs(OUT, exist_ok=True)
    pdf = os.path.join(OUT, f"{fname}_{tag}.pdf")
    png = os.path.join(OUT, f"{fname}_{tag}.png")
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[ok] {png}")
    return png


def plot_summary(root, data, tag):
    conds = [c for c in ["E1A", "E1B", "E2R1", "E2R4", "E2R12", "E3B"] if c in data]
    if len(conds) < 2:
        print("[skip] 图4-5: 有效条件不足")
        return None

    def agg(cond, fn):
        vals = [fn(rows) for _, rows in data[cond]]
        return float(np.mean(vals)), float(min(vals)), float(max(vals))

    specs = [
        ("rumor_related", lambda rows: sum(int(r["rumor_related"]) for r in rows),
         "谣言相关互动总量"),
        ("debunk_related", lambda rows: sum(int(r["debunk_related"]) for r in rows),
         "辟谣/求证相关互动总量"),
        ("interactions", lambda rows: sum(int(r["interactions"]) for r in rows),
         "自发互动总量（不含初始帖）"),
    ]
    x = np.arange(len(conds))
    labels = [STYLE.get(c, (c,))[0] for c in conds]
    colors = [STYLE.get(c, (c, "#666"))[1] for c in conds]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6))
    for ax, (_, fn, name) in zip(axes, specs):
        stats = [agg(c, fn) for c in conds]
        means = np.array([s[0] for s in stats])
        lo = np.array([s[1] for s in stats])
        hi = np.array([s[2] for s in stats])
        ax.bar(x, means, color=colors, alpha=0.85)
        ax.errorbar(x, means, yerr=[means - lo, hi - means], fmt="none",
                    ecolor="#333", capsize=4, lw=1.2)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=38, ha="right", fontsize=8.3)
        ax.set_title(name)
        ax.set_ylabel("条数")
    n_rep = max(len(data[c]) for c in conds)
    sub = "误差线为各重复的极差" if n_rep > 1 else "每组仅 1 次运行，柱高即单次观测值，不代表稳定效应"
    fig.suptitle(f"图 4-5 各实验条件核心指标对比（{sub}）", y=1.05, fontsize=11)
    fig.tight_layout()
    pdf = os.path.join(OUT, f"图4-5_各条件核心指标对比_{tag}.pdf")
    png = os.path.join(OUT, f"图4-5_各条件核心指标对比_{tag}.png")
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[ok] {png}")
    return png


def export_table(root, data, path):
    """导出三组实验的完整数据表（逐轮·逐条件·含重复次数）。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fields = ["group", "rep", "round", "hour_1idx", "posts", "comments", "reposts",
              "likes", "non_interactive", "interactions", "cumulative_interactions",
              "content_rumor", "content_debunk", "content_neutral",
              "engage_rumor", "engage_debunk", "engage_other",
              "rumor_related", "debunk_related"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(fields)
        for cond in sorted(data):
            for rep_name, rows in data[cond]:
                for r in sorted(rows, key=lambda x: int(x["round"])):
                    w.writerow([cond, rep_name] + [r.get(k, "") for k in fields[2:]])
    print(f"[ok] 完整数据表 -> {path}")


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ROOT
    tag = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(root.rstrip("/\\"))
    apply_style()
    data = discover(root)
    print(f"[info] 有效条件: {sorted(data)}  重复数: "
          f"{ {k: len(v) for k, v in data.items()} }")
    nrounds = 16
    plot_panels(root, data, ["E1A", "E2R1", "E2R4", "E2R12"],
                "图 4-1 政府辟谣介入时点对谣言相关互动的影响",
                "图4-1_辟谣介入时点对比", nrounds, tag, required=["E2R1", "E2R4"])
    plot_panels(root, data, ["E1A", "E2R4", "E3B"],
                "图 4-2 政府辟谣回应形态对谣言相关互动的影响",
                "图4-2_辟谣回应形态对比", nrounds, tag, required=["E3B"])
    plot_panels(root, data, ["E1A", "E1B"],
                "图 4-4 谣言形式对传播的影响（E1B 为文本代理刺激）",
                "图4-4_谣言形式对比", nrounds, tag, required=["E1A", "E1B"])
    plot_summary(root, data, tag)
    export_table(root, data,
                 os.path.join(REPO, "mirofish", "results", tag,
                              "summary", "三组实验完整数据表.csv"))


if __name__ == "__main__":
    main()
