# 第六届粤港澳大学生公共治理数据分析大赛 · 数据与推演工作区

> 选题：《极端气象灾害中 AIGC 虚假信息的扩散机理与政务治理回应研究》
> 主切片：2026 年 8 月台风"白海豚"涉灾 AIGC 谣言（case_id `baihaitun_2026`）
> 技术链路：三平台舆情采集 → 文本挖掘 → MiroFish 多智能体反事实推演

---

## 目录地图

```
.
├── docs/                       大赛文档（4 份）
│   ├── 00_参赛指南（简体）.docx
│   ├── 01_实施方案与执行手册（含MiroFish）.docx   ← 总纲
│   ├── 02_团队执行任务与工序依赖总表.docx
│   └── 03_全量案例库（更新扩充版）.docx
│
├── data/                       结构化数据（全部已清洗）
│   ├── 00_meta/                数据字典 · 质量报告 · 采集缺口 · 清洗审计
│   ├── 01_official/            平台一：官方辟谣定性（5 条通报）
│   ├── 02_weibo/               平台二：18 个靶标博文 + 146 条清洗评论 + 18 份原始采集
│   ├── 03_objective/           平台三：客观事实对照组（35 项，含排涝/保供/安置）
│   ├── 04_case_library/        33 起涉灾 AIGC 造谣案例（含分类映射）
│   ├── 05_rumor_corpus/        三台风事件谣言语料（1054 条）+ 可复现脚本 + 图表
│   └── 06_analysis/            情感分析 · LDA 主题 · 交叉表（报告图表的数据底稿）
│
├── mirofish/                   ← 推演层，跑仿真从这里进
│   ├── README.md               部署与注入步骤
│   ├── seed/                   种子材料（MiroFish 直接上传）
│   ├── experiments/            三组反事实实验配置
│   └── outputs/                仿真产物落盘（不入库）
│
├── dist/                       对外分发包（编码已修正）
└── .archive/                   冗余副本与损坏源包（不入库）
```

---

## 数据资产

| 目录 | 内容 | 规模 | 字段要点 |
|---|---|---|---|
| `01_official` | 官方通报全文 | 5 条 | 通报时间、定性措辞、违法标签、处罚人数、客观事实 |
| `02_weibo/core_posts.csv` | 靶标博文（政务号/媒体） | 18 条 | 发布主体、转评赞、评论采集区间 |
| `02_weibo/comments_clean.csv` | 清洗后评论 | 146 条 | 脱敏昵称、清洗文本、分词、点赞/回复数、层级 |
| `02_weibo/comments_excluded.csv` | 剔除记录 | 24 条 | 剔除原因（空/纯表情等） |
| `02_weibo/raw_by_target/` | 原始采集留痕 | 18 组 | 未清洗原文 + 每条采集报告 |
| `03_objective` | 客观事实 | 35 项 | 指标、数值、单位、落区、证据原文、来源链接 |
| `04_case_library` | 案例库 | 33 起 | 场景、手法、表述、真相、危害、处置 |
| `05_rumor_corpus` | 三事件语料 | 1054 条 | 白海豚 378 / 杜苏芮 319 / 摩羯 357，含切片类型与 LDA 结果 |
| `06_analysis` | 分析底稿 | 162 条 | 情感分、主题归属、小时级走势、LDA 主题词 |

`data/05_rumor_corpus/` 内部保留原包结构（`data/` `figures/` `raw/` `scripts/`），
因为其脚本用 `os.path.dirname(__file__)` 解析相对路径，整体平移即可复现，无需改代码。

---

## 从数据到报告的一条线

```
采集 → 清洗 → 描述统计(表3-1) → 情感分析(图3-1) → LDA 主题(图3-2)
                                          ↓
                              MiroFish 种子材料（mirofish/seed/）
                                          ↓
                        三组反事实实验（mirofish/experiments/）
                                          ↓
                    情绪演化曲线 · 抢购参与率 · A/B 形态对比
                                          ↓
                                  报告第 4–5 章
```

---

## MiroFish 怎么开始

1. 读 `mirofish/README.md` → 按第 2 节部署，第 3 节填 `.env`（Key 不入库）
2. 上传 `mirofish/seed/seed_main_baihaitun.md`
3. 先跑 20 agents × 8 轮校准 token 消耗
4. 按 `experiments/` 参数跑正式实验（1 + 3 + 2 = 6 次）

> 上游项目：<https://github.com/666ghj/MiroFish>（AGPL-3.0）。
> 注意其 Python 要求为 3.11–3.12，本机 3.13 需由 uv 另建虚拟环境。

---

## 数据局限（写进报告，别回避）

1. **评论量未达标**：目标 2000–4000 条，实际清洗后 146 条（+16 补充 = 162），达成率 7.3%。
   详见 `data/00_meta/collection_gaps.csv`。
2. **立场分布偏斜**：评论采自辟谣帖下方，"谴责造谣"占 88.9%，不代表全网舆情底噪。
3. **仿真非预测**：MiroFish 输出为反事实推演，不可作真实舆情预测使用。

---

## 路径变更对照（v1 → v2，2026-10-20）

| 原路径 | 现路径 |
|---|---|
| `data/data/platform1_official_debunks.csv` | `data/01_official/official_debunks.csv` |
| `data/data/platform3_objective_facts.csv` | `data/03_objective/objective_facts.csv` |
| `data/data/platform2_core_posts.csv` | `data/02_weibo/core_posts.csv` |
| `data/data/comments_clean.csv` | `data/02_weibo/comments_clean.csv` |
| `data/data/post_statistics.csv` | 已归档（与 `core_posts.csv` 哈希相同） |
| `data/data/platform2_public_comments.csv` | 已归档（与 `comments_clean.csv` 哈希相同） |
| `data/data/platform2_comments_excluded.csv` | 已归档（与 `comments_excluded.csv` 哈希相同） |
| `data/data/platform2_hourly_comments.csv` | 已归档（与 `hourly_counts.csv` 哈希相同） |
| `data/data/*.json` `data_dictionary.csv` | `data/00_meta/` |
| `weibo_comments/weibo_comments/` | `data/02_weibo/raw_by_target/` |
| `数据图表和补充数据集/<乱码目录>/` | `data/06_analysis/` |
| `谣言数据/` | `data/05_rumor_corpus/` |
| 根目录 4 个 `.docx` | `docs/`（重编号） |
| `谣言数据_utf8fix.zip` | `dist/` |
| `谣言数据(1).zip`、`最终数据集与图表.zip` | `.archive/packages/` |
| 三处 `__MACOSX/` | `.archive/trash/` |

被归档的 4 个 csv 与保留版本**逐字节相同**（SHA-256 校验），归档只为消除歧义，未丢数据。
