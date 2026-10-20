# 正式实验运行日志索引（formal_20261021）

> 每组运行均保存：`simulation_config.json`（本组配置）、`simulation.log`（运行日志）、
> `reddit_actions.jsonl`（动作序列，指标的唯一来源）、`run_meta.json`（含干预核验与余额记录）、
> `metrics_per_round.csv`（逐轮指标）、`run_metrics.json`（汇总指标）。

| 目录 | 条件 | 轮次 | 干预 | 干预核验 | 状态 |
|---|---|---|---|---|---|
| `runs/E1A_rep1` | 传统文字谣言 · 无干预（基线） | 16 | 无 | — | 完成 |
| `runs/E1B_rep1` | AIGC 高拟真图文（文本代理） | 16 | 无 | — | 完成 |
| `runs/E2R1_rep1` | 第 1 模拟小时介入（公文式辟谣） | 16 | 第 1 轮注入 | 命中第 1 轮（9 次） | 完成 |
| `runs/E2R4_rep1` | 第 4 模拟小时介入（公文式辟谣） | 16 | 第 4 轮注入 | 命中第 4 轮（9 次） | 完成 |

**未运行**：E2R12（第 12 小时）、E3B（数智实证型辟谣）——DeepSeek 余额耗尽（编排脚本止损阈值 < ¥0.8 自动停止）。

其他文件：
- `0_pristine_config.json`：未做任何覆写前的原始仿真配置（供对照审计）
- `summary/`：`all_runs_metrics.csv`、`by_condition_metrics.csv`、`per_round_long.csv`、`analysis_manifest.json`
- `batch_summary.json`：批次汇总（含每次运行的余额变化）

大体积原始数据库与完整运行副本保留在本地 `Desktop/MiroFish/backend/uploads/simulations/sim_285f7fdfd644/`（不入库）。
