#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""表 3-1：样本统计标准三线表（CSV + 三线表样式图）。"""
import os, json, csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, 'data')
FIG = os.path.join(BASE, 'figures')
plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Arial Unicode MS']

EVENTS = ['白海豚', '杜苏芮', '摩羯台风AI造假']
LABEL = {'白海豚': '白海豚', '杜苏芮': '杜苏芮', '摩羯台风AI造假': '摩羯台风谣言与AI造假'}


def main():
    st = json.load(open(os.path.join(BASE, 'raw', 'stats.json'), encoding='utf-8'))
    rows, tot, spans = [], {'raw': 0, 'drop': 0, 'valid': 0}, []
    for e in EVENTS:
        s = st['stats'][e]
        valid = s['valid']
        dropped = sum(st['drop'].get(e, {}).values())
        total_raw = valid + dropped
        keep = valid / total_raw * 100 if total_raw else 0
        span = f"{s['span'][0]} — {s['span'][1]}" if s['span'][0] else '—'
        rows.append([LABEL[e], total_raw, dropped, valid, f'{keep:.1f}%', span])
        spans.append(span)
        tot['raw'] += total_raw
        tot['drop'] += dropped
        tot['valid'] += valid
    rows.append(['合计', tot['raw'], tot['drop'], tot['valid'],
                 f"{tot['valid']/tot['raw']*100:.1f}%",
                 f"{min(x.split(' — ')[0] for x in spans)} — {max(x.split(' — ')[1] for x in spans)}"])

    header = ['事件标签', '样本总量（条）', '清洗剔除量（条）', '有效样本量（条）', '留存率', '时间跨度']
    fp = os.path.join(DATA, '表3-1_样本统计三线表.csv')
    with open(fp, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print('CSV 已生成:', fp)
    for r in rows:
        print(r)

    # ---------- 三线表渲染 ----------
    fig = plt.figure(figsize=(12.6, 3.6), facecolor='white')
    head_y = 0.74
    row_h = 0.115
    x = [0.035, 0.225, 0.385, 0.555, 0.705, 0.785]
    align = ['left', 'center', 'center', 'center', 'center', 'left']

    fig.text(0.04, 0.90, '表 3-1  灾害 AIGC 谣言舆情样本采集与清洗统计', fontsize=13.5,
             fontweight='600', ha='left', va='center')

    # 三线：顶线（粗）、栏目线（细）、底线（粗）
    fig.add_artist(Line2D([0.028, 0.995], [0.815, 0.815], color='black', lw=2.0))
    fig.add_artist(Line2D([0.028, 0.995], [0.705, 0.705], color='black', lw=0.9))
    fig.add_artist(Line2D([0.028, 0.995], [0.705 - row_h * len(rows) - 0.03] * 2, color='black', lw=2.0))

    for xi, h, al in zip(x, header, align):
        fig.text(xi, head_y, h, fontsize=10.6, fontweight='600', ha=al, va='center')

    for i, r in enumerate(rows):
        y = head_y - row_h * (i + 1) - 0.012
        bold = (r[0] == '合计')
        for xi, v, al in zip(x, r, align):
            fig.text(xi, y, str(v), fontsize=10.3, ha=al, va='center',
                     fontweight='700' if bold else 'normal')

    fig.text(0.04, 0.055, '注：样本总量为检索命中的全部原始条目（含博文与评论）；剔除含事件无关、同名噪声、广告导流、'
                          '同用户重复、跨账号重复文本等；留存率＝有效样本量／样本总量。',
             fontsize=8.6, color='#555555', ha='left', va='center')

    out = os.path.join(FIG, '表3-1_样本统计三线表.png')
    fig.savefig(out, dpi=300, facecolor='white')
    fig.savefig(out.replace('.png', '.pdf'), facecolor='white')
    print('三线表图已导出:', out)


if __name__ == '__main__':
    main()
