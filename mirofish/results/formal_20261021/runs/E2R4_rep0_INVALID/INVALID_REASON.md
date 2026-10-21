# E2R4_rep0_INVALID 作废说明

## 结论
该次运行**不可用于任何组间比较**，已从正式数据集中剔除，改名为 E2R4_rep0_INVALID 仅作留痕。

## 证据
1. `process_stdout.txt` 中出现 30 次
   `openai.APIStatusError: Error code: 402 - {'error': {'message': 'Insufficient Balance'}}`，
   说明运行后段 DeepSeek 账户余额不足，模型调用失败。
2. `reddit_actions.jsonl` 中 **round 12–16 完全没有任何动作记录**（既无互动动作，也无 DO_NOTHING），
   而同批次 E1A / E1B / E2R1 在 round 16 仍有动作。
3. `process_stdout.txt` 记录总动作 144，低于 E2R1 的 159（同为 16 轮），确认为中断而非自然收敛。
4. `run_meta.json`: balance_after = ¥0.56，随后延迟入账至 −¥0.13。

## 影响
此前"第 4 小时介入后谣言相关互动连续 12 轮为 0"这一表述**是预算耗尽造成的假象，
不是辟谣效果**，已在论文中撤回并改由重跑数据替代。
