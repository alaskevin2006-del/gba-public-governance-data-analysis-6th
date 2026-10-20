# MiroFish 跑通指南

面向本项目的配置步骤。目标：用 `seed/` 下的种子材料跑出三组反事实推演，
产物直接作为参赛报告第 4 章的实证图表。

- 上游项目：<https://github.com/666ghj/MiroFish>（AGPL-3.0，盛大集团孵化）
- 仿真底座：CAMEL-AI [OASIS](https://github.com/camel-ai/oasis)，Agent 长期记忆走 Zep Cloud
- 本地在线 Demo（免部署先看效果）：<https://666ghj.github.io/mirofish-demo/>

---

## 0. 本目录约定

```
mirofish/
├── README.md                        ← 本文件
├── seed/                            种子材料（上传给 MiroFish）
│   ├── seed_main_baihaitun.md       主种子：官方定性 + 造谣样本 + 客观事实 + 50 条热评
│   ├── inject_scenario_A_公文辟谣.md 实验三对照组注入文本
│   └── inject_scenario_B_数智实证.md 实验三实验组注入文本
├── experiments/                     三组实验的配置参数表
│   ├── exp1_baseline_diffusion.md
│   ├── exp2_golden_window.md
│   └── exp3_response_form.md
└── outputs/                         仿真报告与日志落盘（已 gitignore）
```

---

## 1. 前置检查

| 依赖 | 要求 | 本机核对命令 |
|---|---|---|
| Node.js | 18+ | `node -v` |
| Python | **3.11 – 3.12**（不支持 3.13） | `python --version` |
| uv | 最新版 | `uv --version` |
| Docker | 仅容器部署需要 | `docker -v` |
| 内存 | 16 GB+，建议 32 GB | — |
| 磁盘 | ≥ 5 GB（镜像 + 图谱库 + 日志） | — |

> ⚠️ **本机 Python 是 3.13.13，高于 MiroFish 上限**。
> `npm run setup:backend` 会用 uv 自动拉一个 3.12 的虚拟环境，正常情况下不受影响；
> 若报依赖解析失败，手动指定：`uv venv --python 3.12 backend/.venv`。

---

## 2. 部署（二选一）

### 2.1 Docker 方式（推荐，环境干净）

```bash
git clone https://github.com/666ghj/MiroFish.git
cd MiroFish
cp .env.example .env      # 按第 3 节填 Key
docker compose up --build -d
```

启动后：前端 <http://localhost:3000>　后端 <http://localhost:5001>

### 2.2 源码方式

```bash
git clone https://github.com/666ghj/MiroFish.git
cd MiroFish
cp .env.example .env
npm run setup:all         # 一次性装 root + frontend + backend 依赖
npm run dev               # 前后端同启
```

---

## 3. `.env` 配置

```ini
# ── 大模型（OpenAI SDK 兼容格式即可）────────────────────
# 推荐：阿里云百炼 Qwen-Plus
LLM_API_KEY=sk-xxxxxxxx
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus

# 或 DeepSeek
# LLM_BASE_URL=https://api.deepseek.com/v1
# LLM_MODEL_NAME=deepseek-chat
```

**记忆后端：Zep Cloud（必选项）**

```ini
GRAPH_BACKEND=zep
ZEP_API_KEY=zep_xxxxxxxx
```

> ⚠️ **更正（2026-10-20，经源码核实 @7657031）**：早前假设的"方案二本地图谱
> （Neo4j+Qdrant）"在 MiroFish 当前代码中**不存在**——grep 无任何
> `GRAPH_BACKEND`/`neo4j`/`qdrant` 引用，`backend/app/config.py` 的
> `Config.validate()` 强制要求 `LLM_API_KEY` 与 `ZEP_API_KEY` **同时存在**，
> 缺一即拒绝启动。Zep Cloud 免费额度按调用次数计，预算敏感时优先压低
> Agent 数与轮次（先 8 轮烟雾测试校准），而非切换不存在的本地后端。

> 🔒 **Key 不进仓库**。`.env` 已在 `.gitignore` 内；任何截图、录屏、提交前都要确认 Key 不可见。

---

## 4. 跑一次的最小路径

1. 打开 <http://localhost:3000> → **新建模拟**
2. **上传种子材料**：`seed/seed_main_baihaitun.md`
   - 若上传失败或抽取实体过少，改成分段上传：§1+§2 → §3+§4 → §5
3. **填写预测需求**（直接复制，别改措辞）：
   ```
   在无政务干预的条件下，涉台风"白海豚"AI 造假灾情信息在社交平台扩散后，
   公众恐慌情绪何时达到峰值？愿意参与线下物资抢购的群体比例是多少？
   请给出情绪演化曲线与抢购行为占比。
   ```
4. 等系统构建：知识图谱 → 实体关系抽取 → Agent 人设生成（首次约 5–15 分钟）
5. **Agent 数量与轮次**：先跑 **20 agents × 8 轮** 校准 token 消耗；
   确认可接受后再放大到 `experiments/` 里的正式参数
6. 运行 → 等 ReportAgent 生成报告 → 导出
7. 产物落盘到 `mirofish/outputs/exp{N}_{日期}/`，连同 `交互日志.csv` 一起存

---

## 5. 三组实验怎么落地

| 实验 | 变量 | 做法 | 详见 |
|---|---|---|---|
| 实验一 基准扩散 | 无干预 | 只注入主种子，不注入任何官方通报 | `experiments/exp1_baseline_diffusion.md` |
| 实验二 黄金窗口 | 介入时点 1h / 4h / 12h | 同一主种子跑 3 次，仅在注入时点不同 | `experiments/exp2_golden_window.md` |
| 实验三 回应形态 | 公文辟谣 vs 数智实证 | 同一时点（建议 4h）注入 A 版 / B 版文本 | `experiments/exp3_response_form.md` |

**共 6 次运行**（1 + 3 + 2）。每次运行前先 `新建模拟`，避免图谱串味。

**固定不变量**（否则结果不可比）：

- 同一个 `LLM_MODEL_NAME`
- 同一份主种子文件
- Agent 总数与七类画像占比（见主种子 §7）
- 轮次上限 15
- 随机种子（若界面支持）

---

## 6. 常见坑

| 现象 | 原因 | 处理 |
|---|---|---|
| `npm run setup:backend` 依赖解析失败 | Python 3.13 超出范围 | `uv venv --python 3.12` 后重装 |
| 图谱里只有零星实体 | 种子文档过长被截断 | 分段上传，或在预测需求里点名关键实体（浦东、金山、鄞州） |
| Agent 说话像客服，没有立场差异 | 画像未被充分注入 | 在主种子 §7 基础上，于界面手工加权"社区长辈""营销号"比例 |
| 跑了 3 轮就几乎没互动 | 平台活跃度参数过低 | 调高发帖频率 / 增加 Agent 数到 60+ |
| Token 消耗远超预期 | 轮次过多或 agent 过多 | 15 轮是上限不是目标；先用 8 轮出形状 |
| 报告全是套话 | ReportAgent 拿不到结构化数据 | 在预测需求里明确要求"输出情绪曲线数据点与抢购占比数值" |
| Zep 报额度不足 | 免费额度按调用计 | 压低 Agent 数与轮次重试；**不存在本地图谱备选**（上游 @7657031 无 GRAPH_BACKEND=local，已核实） |

---

## 7. 产物如何进报告

| 报告位置 | 取用内容 |
|---|---|
| 第 4 章 实验设计 | `experiments/*.md` 的参数表 → 改写成方法段落 |
| 第 4 章 结果 | ReportAgent 输出的情绪演化曲线、抢购占比、信任评分变化 |
| 第 4 章 对比 | 实验二三条曲线叠加图；实验三 A/B 双曲线 |
| 第 5 章 对策 | 用实验二的拐点位置论证"1–2 小时黄金窗口" |
| 附录 | 交互日志节选（脱敏后）、种子材料全文 |

---

## 8. 合规红线（跑之前再确认一遍）

- 种子材料中的网民信息已脱敏，**不要在界面手工补真实昵称或主页链接**。
- 仿真截图入报告前，检查是否带出 `localhost` 之外的任何 Key、邮箱、真实账号。
- 报告须写明"仿真为反事实推演，非真实舆情预测"，见主种子 §8.3。
- MiroFish 为 AGPL-3.0，**引用其代码或二次分发需遵守该协议**；仅使用产物做分析不构成分发。
