"""
表 2-2：客观事实与虚假险情对照三线表
来源：data/01_official/official_debunks.csv（定性）+ data/03_objective/objective_facts.csv（数据）
规则：每行虚假表述必须能对应到官方通报 record_id；客观数据列必须给出 P3-xxx record_id。
输出：deliverables/tables/表2-2_客观事实与虚假险情对照.csv + .pdf + .png
"""
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mirofish", "scripts"))
from style_config import apply_style

REPO = "C:/Users/Kevin/Desktop/gba-public-governance-data-analysis-6th"
OUT_CSV = f"{REPO}/deliverables/tables/表2-2_客观事实与虚假险情对照.csv"
OUT_PDF = f"{REPO}/deliverables/tables/表2-2_客观事实与虚假险情对照.pdf"
OUT_PNG = f"{REPO}/deliverables/tables/表2-2_客观事实与虚假险情对照.png"

# 人工编排的对照关系（每行给出双方 record_id，保证可审计）
ROWS = [
    # (虚假险情表述, 谣言来源record_id, 手法, 官方定性要点, 客观事实摘要, 数据record_ids, 对冲逻辑)
    ("浦东一女子在台风中坠楼（配坠落视频）", "P1-01/P1-02", "AI 合成",
     "视频系 60 岁高某某用 AI 软件生成；浦东未发生该事件",
     "全市平均雨量 268.5mm、徐家汇站 316.1mm（真实灾情严重但无坠楼通报对应事件）",
     "P3-034;P3-035", "以真实降雨量级区分'灾情真实'与'险情虚构'"),
    ("安置点停水停电、受灾人员打地铺吃不上饭", "P1-02/P1-04", "虚构灾情",
     "宁波鄞州 5 起涉灾谣言被查处；上海 11 起案件 12 人被处罚",
     "金山 74 处安置点、转移 6000 人、物资 1800 件、24h 热水+免费客饭、驻守警力 4 名",
     "P3-028;P3-029;P3-030;P3-031;P3-032;P3-033", "以安置保障实数对冲'断水断电'断言"),
    ("全城被淹/多地积水成灾（黄鹂新村、瞻岐镇、杨浦'又发大水'）", "P1-02/P1-03", "旧闻翻炒",
     "积水视频系往年旧视频或他人 7 月 18 日暴雨视频重编",
     "121 座水闸联排、累计 1311 闸次、排水 8 亿 m³；浦东 300 座泵站、排水 5571 万 m³",
     "P3-019;P3-020;P3-021;P3-022;P3-016;P3-017", "以排涝调度实载说明内涝处置能力"),
    ("坐标：上海金山（外省积水视频）/嘉定酒店车库被淹/广富林房屋被淹", "P1-04", "跨地拼接/景观误标",
     "视频为外省往年素材拼接或文旅景观误标，4 名造谣者被行拘",
     "浦东市级泵车 32 台、区级抢险班组 260 个；惠南镇抢险 16 人/抽水泵 13 台",
     "P3-013;P3-015;P3-010;P3-012", "以抢险力量在位数据对冲'救援失能'暗示"),
    ("全城餐饮停业、骑手补贴等虚假通知", "P1-05", "借灾引流/虚假宣传",
     "官方未发布此类通知，属借灾引流起号",
     "生活必需品备货量较日常 +50%；库存充足、不断档不缺货；价格总体平稳",
     "P3-025;P3-026;P3-027", "以保供实数对冲'物资断供'恐慌"),
    ("白海豚还没来楼已塌（温州）", "P1-05", "建筑误读",
     "实为泽雅镇文旅地标艺术造型，发布者被教育训诫",
     "台风 8-09 17:30 才在玉环登陆（14 级）、18:40 乐清二次登陆（13 级）",
     "P3-003;P3-004", "以预警/登陆时序拆穿'未到先塌'的时间造假"),
]


def main():
    df = pd.DataFrame(ROWS, columns=[
        "虚假险情表述", "谣言定性来源", "造谣手法", "官方核实结论",
        "客观事实与数据", "数据来源编号", "对冲逻辑",
    ])
    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"CSV: {len(df)} 行 → {OUT_CSV}")

    # 三线表 PDF/PNG
    apply_style()
    fig, ax = plt.subplots(figsize=(16, 6.5))
    ax.axis("off")
    cell_text = [[r[0], r[2], r[3], r[4]] for r in ROWS]
    col_labels = ["虚假险情表述", "造谣手法", "官方核实结论", "客观事实与数据"]
    col_w = [0.24, 0.12, 0.28, 0.36]
    tbl = ax.table(cellText=cell_text, colLabels=col_labels, colWidths=col_w,
                   cellLoc="left", loc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9.5)
    # 三线表样式：只留顶线、表头线、底线
    for (row, col), cell in tbl.get_celld().items():
        cell.set_edgecolor("none")
        cell.set_height(0.13)
        if row == 0:
            cell.set_text_props(weight="bold")
            cell.set_edgecolor("black")
            cell.set_linewidth(1.2)
            cell.visible_edges = "TB"
    n = len(ROWS)
    # 顶线与底线
    ax.plot([0, 1], [0.985, 0.985], color="black", lw=1.6, transform=ax.transAxes, clip_on=False)
    ax.plot([0, 1], [0.015, 0.015], color="black", lw=1.6, transform=ax.transAxes, clip_on=False)
    ax.set_title("表 2-2 台风“白海豚”涉灾 AIGC 虚假险情与客观事实对照表", fontsize=13, pad=18)
    fig.tight_layout()
    fig.savefig(OUT_PDF, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=300, bbox_inches="tight")
    print(f"PDF/PNG 已导出 → {OUT_PDF}")


if __name__ == "__main__":
    main()
