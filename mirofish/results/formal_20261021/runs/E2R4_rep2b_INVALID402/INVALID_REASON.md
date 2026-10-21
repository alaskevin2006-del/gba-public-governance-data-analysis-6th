# E2R4_rep2b_INVALID402 作废说明

本批次（补跑批次）的 E2R4_rep2，与上一批次的同名运行区分，故加后缀 b。

## 判定
不可用于任何比较。该次运行在 DeepSeek 账户余额不足的情况下执行，模型调用返回
HTTP 402 Insufficient Balance。

## 证据
- `process_stdout.txt` 中 402 次数：**20**
- 有动作的轮次：14/16
- 缺失轮次：[14, 15, 16]
- 完成度审计状态：`INVALID(402x20)`
