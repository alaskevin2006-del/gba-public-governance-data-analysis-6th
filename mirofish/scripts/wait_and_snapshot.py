#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
等待后端当前仿真真正完成，再把真实产物快照到结果目录。

背景（2026-10-20 踩坑）：
  对同一 simulation_id 连续跑 A/B 两组时，/run-status 会保留上一组的
  completed 状态（current_round=8 / progress=100 / actions=181），
  导致 wait_simulation 立即返回 → 快照到的是上一组的陈旧文件（B 组日志为 0 字节）。
  因此本脚本改为直接监测后端磁盘产物：
    1. simulation.log 出现"模拟循环完成"
    2. <platform>/actions.jsonl 的 mtime 停止增长（连续 N 次不变）

用法：
  python wait_and_snapshot.py --simulation-id sim_xxx --out-dir <results>/B --timeout 1800
"""
import argparse
import json
import os
import shutil
import time

BACKEND_UPLOADS = os.path.join(
    os.path.expanduser("~"), "Desktop", "MiroFish", "backend", "uploads", "simulations"
)

FILES = [
    ("simulation_config.json", "simulation_config.json"),
    ("simulation.log", "simulation.log"),
    ("twitter/actions.jsonl", "twitter_actions.jsonl"),
    ("reddit/actions.jsonl", "reddit_actions.jsonl"),
]


def wait_complete(sim_dir: str, timeout: int, stable_checks: int = 3) -> bool:
    log = os.path.join(sim_dir, "simulation.log")
    # 监视的动作文件：优先 Twitter，若未启用 Twitter（单平台 reddit 运行）则用 Reddit
    act = os.path.join(sim_dir, "twitter", "actions.jsonl")
    if not os.path.exists(act):
        act = os.path.join(sim_dir, "reddit", "actions.jsonl")
    start = time.time()
    last_size, stable = -1, 0
    while time.time() - start < timeout:
        done = False
        if os.path.exists(log):
            try:
                txt = open(log, encoding="utf-8", errors="ignore").read()
                done = "模拟循环完成" in txt
            except Exception:
                pass
        size = os.path.getsize(act) if os.path.exists(act) else -1
        if size == last_size and size > 0:
            stable += 1
        else:
            stable = 0
        last_size = size

        if done and stable >= stable_checks:
            print(f"[wait] 完成标记已出现且 actions.jsonl 稳定 ({size} 字节)")
            return True
        print(f"[wait] log_done={done} actions_size={size} stable={stable} "
              f"elapsed={int(time.time()-start)}s")
        time.sleep(30)
    print(f"[wait] 超时 {timeout}s")
    return False


def snapshot(sim_dir: str, out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    copied = {}
    for rel, fname in FILES:
        s = os.path.join(sim_dir, rel)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(out_dir, fname))
            copied[fname] = os.path.getsize(s)
    return copied


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulation-id", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--timeout", type=int, default=1800)
    a = ap.parse_args()

    sim_dir = os.path.join(BACKEND_UPLOADS, a.simulation_id)
    ok = wait_complete(sim_dir, a.timeout)
    copied = snapshot(sim_dir, a.out_dir)
    print("快照:", json.dumps(copied, ensure_ascii=False))

    # 校验：干预帖是否真的进入本次运行
    for plat in ("twitter_actions.jsonl", "reddit_actions.jsonl"):
        p = os.path.join(a.out_dir, plat)
        if not os.path.exists(p):
            continue
        n_debunk = 0
        n_total = 0
        for line in open(p, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("action_type"):
                n_total += 1
                if "情况通报" in json.dumps(d.get("action_args", {}), ensure_ascii=False):
                    n_debunk += 1
        print(f"  {plat}: 动作 {n_total} 条，含官方辟谣帖 {n_debunk} 条")
    print("WAIT_OK" if ok else "WAIT_TIMEOUT")


if __name__ == "__main__":
    main()
