# -*- coding: utf-8 -*-
"""
为 MiroFish @7657031 的运行器打补丁（LKX 2026-10-20）

补丁内容（三项，均为最小改动）：
  P1 实现上游声明但未消费的 event_config.scheduled_events：
     在指定轮次进入 Agent 动作之前，向选定 Agent 注入一条 CREATE_POST 手动动作。
     用于实现"政府辟谣于模拟第 k 小时注入"的真实干预。
  P2 支持 simulation_config.random_seed → Python random.seed()，
     使 Agent 激活选择在 Python 侧可复现（LLM 采样本身仍不可复现）。
  P3 注入动作不手工写 actions.jsonl（避免与 DB 抓取重复计数），
     仅在 simulation.log 留痕 "LKX定时事件注入 round=N: K条"。

用法： python apply_runner_patch.py   （幂等，重复执行不会叠加补丁）
"""
import os
import shutil
import sys

BACKEND = r"C:/Users/Kevin/Desktop/MiroFish/backend"
TARGET = os.path.join(BACKEND, "scripts", "run_parallel_simulation.py")
BACKUP = TARGET + ".orig_lkx_20261020"
PATCH_DIR = os.path.join(r"C:/Users/Kevin/Desktop/gba-public-governance-data-analysis-6th",
                         "mirofish", "patches")

MARKER = "# [LKX-PATCH] scheduled_events 支持（补齐上游未实现字段）"

HELPER = MARKER + '''

def lkx_get_scheduled_events(config: Dict[str, Any], round_num: int) -> List[Dict[str, Any]]:
    """取本轮应注入的定时事件。事件格式：
    {"round": k, "agent_id": i, "content": "...", "tag": "..."}
    round 与主循环轮次对齐（round=1 表示第 1 轮，约对应模拟第 1 小时）。"""
    ec = config.get("event_config") or {}
    events = ec.get("scheduled_events") or []
    out = []
    for ev in events:
        try:
            if int(ev.get("round", -1)) == round_num:
                out.append(ev)
        except (TypeError, ValueError):
            continue
    return out

'''


def apply():
    src = open(TARGET, encoding="utf-8").read()
    if MARKER in src:
        print("[skip] 补丁已存在，跳过")
        return 0

    if not os.path.exists(BACKUP):
        shutil.copy2(TARGET, BACKUP)
        print(f"[backup] {BACKUP}")

    # ---- P1a: 注入辅助函数 ----
    anchor = "class PlatformSimulation:"
    assert anchor in src, "找不到 PlatformSimulation 锚点"
    src = src.replace(anchor, HELPER + anchor, 1)

    # ---- P1b: 主循环注入（twitter + reddit 两处相同代码块）----
    loop_anchor = (
        "        # 无论是否有活跃agent，都记录round开始\n"
        "        if action_logger:\n"
        "            action_logger.log_round_start(round_num + 1, simulated_hour)\n"
    )
    inject_block = loop_anchor + '''
        # [LKX-PATCH] 定时事件注入：在 Agent 自主动作之前发布指定内容
        lkx_events = lkx_get_scheduled_events(config, round_num + 1)
        lkx_injected = False
        if lkx_events:
            lkx_actions = {}
            for ev in lkx_events:
                aid = ev.get("agent_id", 0)
                content = ev.get("content", "")
                try:
                    _a = result.env.agent_graph.get_agent(aid)
                    lkx_actions[_a] = ManualAction(
                        action_type=ActionType.CREATE_POST,
                        action_args={"content": content}
                    )
                except Exception as e:
                    log_info(f"[LKX] 定时事件注入失败 round={round_num + 1} agent={aid}: {e}")
            if lkx_actions:
                await result.env.step(lkx_actions)
                lkx_injected = True
                log_info(f"LKX定时事件注入 round={round_num + 1}: {len(lkx_actions)}条"
                         + (f" tag={lkx_events[0].get('tag', '')}" if lkx_events else ""))
'''
    n_inject = src.count(loop_anchor)
    if n_inject != 2:
        print(f"[warn] 期望 2 处主循环锚点，实际 {n_inject} 处")
    src = src.replace(loop_anchor, inject_block)

    # ---- P1c: 空活跃轮也要抓取注入动作 ----
    empty_anchor = (
        "        if not active_agents:\n"
        "            # 没有活跃agent时也记录round结束（actions_count=0）\n"
        "            if action_logger:\n"
        "                action_logger.log_round_end(round_num + 1, 0)\n"
        "            continue\n"
    )
    empty_new = (
        "        if not active_agents and not lkx_injected:\n"
        "            # 没有活跃agent时也记录round结束（actions_count=0）\n"
        "            if action_logger:\n"
        "                action_logger.log_round_end(round_num + 1, 0)\n"
        "            continue\n"
        "        \n"
        "        if not active_agents and lkx_injected:\n"
        "            # [LKX-PATCH] 注入已发生但无自主动作时，仍需把注入动作落盘\n"
        "            inj_rows, last_rowid = fetch_new_actions_from_db(db_path, last_rowid, agent_names)\n"
        "            inj_count = 0\n"
        "            for action_data in inj_rows:\n"
        "                if action_logger:\n"
        "                    action_logger.log_action(\n"
        "                        round_num=round_num + 1,\n"
        "                        agent_id=action_data['agent_id'],\n"
        "                        agent_name=action_data['agent_name'],\n"
        "                        action_type=action_data['action_type'],\n"
        "                        action_args=action_data['action_args']\n"
        "                    )\n"
        "                    total_actions += 1\n"
        "                    inj_count += 1\n"
        "            if action_logger:\n"
        "                action_logger.log_round_end(round_num + 1, inj_count)\n"
        "            continue\n"
    )
    n_empty = src.count(empty_anchor)
    if n_empty != 2:
        print(f"[warn] 期望 2 处空轮锚点，实际 {n_empty} 处")
    src = src.replace(empty_anchor, empty_new)

    # ---- P2: 随机种子 ----
    seed_anchor = "    config = load_config(args.config)\n"
    seed_new = (
        "    config = load_config(args.config)\n"
        "    # [LKX-PATCH] 随机种子（仅决定 Python 侧激活抽样；LLM 采样本身不可复现）\n"
        "    _lkx_seed = config.get(\"random_seed\")\n"
        "    if _lkx_seed is not None:\n"
        "        try:\n"
        "            random.seed(int(_lkx_seed))\n"
        "            print(f\"[LKX] random_seed={_lkx_seed} 已生效\")\n"
        "        except (TypeError, ValueError):\n"
        "            pass\n"
    )
    src = src.replace(seed_anchor, seed_new, 1)

    open(TARGET, "w", encoding="utf-8").write(src)
    print(f"[ok] 已打补丁: {TARGET}")

    # 保存补丁副本与 diff 到仓库
    os.makedirs(PATCH_DIR, exist_ok=True)
    shutil.copy2(BACKUP, os.path.join(PATCH_DIR, "run_parallel_simulation.py.orig"))
    print(f"[ok] 补丁文件与原件已存入 {PATCH_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(apply())
