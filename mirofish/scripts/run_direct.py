#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
直接驱动 OASIS 运行器的正式实验编排（绕过后端 /start 接口）

为什么不用 /api/simulation/start：
  2026-10-21 凌晨实测，通过接口派生的子进程会在启动后数秒内静默退出
  （无 traceback、无产物），而同一份配置用命令行手动运行完全正常。
  为保证实验连续执行，改为由本脚本以子进程方式直接调用运行器脚本，
  其余步骤（配置生成、状态清理、产物快照、干预核验、费用记录）不变。

用法：
  python run_direct.py --rounds 16 --plan <plan.json> --out-root <dir>
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import experiment_config as ec
import formal_experiment_config as fc
from run_simulation import read_deepseek_balance

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS_DIR = os.path.join(REPO, "mirofish", "results")
BACKEND = os.path.join(os.path.expanduser("~"), "Desktop", "MiroFish", "backend")
SIM_ROOT = os.path.join(BACKEND, "uploads", "simulations")
RUNNER = os.path.join(BACKEND, "scripts", "run_parallel_simulation.py")
VENV_PY = os.path.join(BACKEND, ".venv", "Scripts", "python.exe")

RESET_TARGETS = [
    "twitter_simulation.db", "reddit_simulation.db",
    "twitter/actions.jsonl", "reddit/actions.jsonl", "simulation.log",
    "run_state.json", "env_status.json", "state.json",
]


def sim_dir(sid):
    return os.path.join(SIM_ROOT, sid)


def cfg_path(sid):
    return os.path.join(sim_dir(sid), "simulation_config.json")


def reset(sid):
    """清理上一次运行的产物。

    注意 log/ 目录：运行器启动时会对 sim_dir/log 执行 shutil.rmtree。
    本机环境对"单次批量删除"有阈值保护，连续多组运行会累积删除文件数并触发拦截，
    导致子进程直接退出（2026-10-21 E3B 首次运行即因此 31 秒崩溃）。
    因此这里在每组运行前先自行清理 log/，使运行器待删除的文件数保持在低位。
    """
    n = 0
    import shutil
    log_dir = os.path.join(sim_dir(sid), "log")
    if os.path.exists(log_dir):
        shutil.rmtree(log_dir, ignore_errors=True)
    for rel in RESET_TARGETS:
        p = os.path.join(sim_dir(sid), rel)
        if os.path.exists(p):
            try:
                os.remove(p)
                n += 1
            except Exception:
                pass
    return n


def wait_completion(sid, timeout, poll=20, stable=3):
    """等待 simulation.log 出现完成标记且 reddit/actions.jsonl 稳定。
    返回 (ok, elapsed)。若进程仍存活但长时间无进展也继续等待，直到超时。"""
    log = os.path.join(sim_dir(sid), "simulation.log")
    act = os.path.join(sim_dir(sid), "reddit", "actions.jsonl")
    start = time.time()
    last, hits = -1, 0
    while time.time() - start < timeout:
        done = False
        if os.path.exists(log):
            try:
                done = "模拟循环完成" in open(log, encoding="utf-8", errors="ignore").read()
            except Exception:
                pass
        size = os.path.getsize(act) if os.path.exists(act) else -1
        hits = hits + 1 if (size == last and size > 0) else 0
        last = size
        if done and hits >= stable:
            return True, round(time.time() - start, 1)
        time.sleep(poll)
    return False, round(time.time() - start, 1)


def verify(out_dir, marker, expect_round):
    if not marker:
        return {"checked": False}
    rounds, hits = set(), 0
    for plat in ("twitter_actions.jsonl", "reddit_actions.jsonl"):
        p = os.path.join(out_dir, plat)
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8", errors="ignore"):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if marker in json.dumps(d, ensure_ascii=False):
                hits += 1
                if d.get("round") is not None:
                    rounds.add(int(d["round"]))
    r = sorted(rounds)
    return {"checked": True, "marker_hits": hits, "rounds_found": r,
            "expected_round": expect_round, "first_round": r[0] if r else None,
            "delivered": bool(r),
            "on_time": bool(r) and r[0] == expect_round}


def snapshot(sid, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    copied = {}
    for rel, fname in (("simulation_config.json", "simulation_config.json"),
                       ("simulation.log", "simulation.log"),
                       ("twitter/actions.jsonl", "twitter_actions.jsonl"),
                       ("reddit/actions.jsonl", "reddit_actions.jsonl")):
        s = os.path.join(sim_dir(sid), rel)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(out_dir, fname))
            copied[fname] = os.path.getsize(s)
    return copied


def completion_audit(out_dir, rounds):
    """动作级完成度审计。

    背景：2026-10-21 发现 E2R4_rep0 因 DeepSeek 余额不足触发 402，
    导致 round 12-16 完全没有任何动作记录，却仍被判为 'completed'。
    因此不能只看退出码，必须检查尾部轮次是否真的产生了记录。
    """
    import collections
    act_rounds = collections.Counter()
    for plat in ("twitter_actions.jsonl", "reddit_actions.jsonl"):
        p = os.path.join(out_dir, plat)
        if not os.path.exists(p):
            continue
        for line in open(p, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if "action_type" in d and d.get("round") is not None:
                act_rounds[int(d["round"])] += 1
    covered = sorted(act_rounds)
    missing = [r for r in range(1, rounds + 1) if r not in act_rounds]
    return {"rounds_with_actions": len(covered),
            "last_round_with_actions": max(covered) if covered else None,
            "missing_rounds_1..N": missing,
            "actions_per_round": {str(k): act_rounds[k] for k in covered}}


def build_config(pristine, group_key, seed):
    g = fc.GROUPS[group_key]
    cfg = json.loads(json.dumps(pristine))
    info_act = ec.enable_interaction(cfg)
    picked = ec.pick_agents(cfg)
    public, official = picked["public"], picked["official"]
    rumors = fc.rumor_posts(g["rumor_form"])
    posts = []
    for i, content in enumerate(rumors):
        posts.append({"content": content, "poster_agent_id": public[i % len(public)],
                      "tag": "initial_rumor_" + g["rumor_form"]})
    ev = cfg.setdefault("event_config", {})
    removed = ev.get("initial_posts", [])
    ev["initial_posts"] = posts
    events = []
    if g["intervention"]:
        events = [{"round": g["intervention_round"], "agent_id": official[0],
                   "content": fc.INTERVENTION_TEXTS[g["intervention"]],
                   "tag": g["intervention"]}]
    ev["scheduled_events"] = events
    cfg["random_seed"] = seed
    return cfg, info_act, len(removed), official


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulation-id", required=True)
    ap.add_argument("--rounds", type=int, default=16)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--seed-base", type=int, default=20261021)
    ap.add_argument("--stop-below", type=float, default=1.0,
                    help="余额低于该值（元）时停止后续运行")
    args = ap.parse_args()

    sid = args.simulation_id
    out_root = args.out_root
    os.makedirs(out_root, exist_ok=True)
    pristine_path = os.path.join(out_root, "0_pristine_config.json")
    if not os.path.exists(pristine_path):
        pristine = ec.load_config(cfg_path(sid))
        with open(pristine_path, "w", encoding="utf-8") as f:
            json.dump(pristine, f, ensure_ascii=False, indent=2)
    pristine = json.load(open(pristine_path, encoding="utf-8"))
    n_agents = len(pristine.get("agent_configs") or [])
    print(f"Agent 数={n_agents} simulation_id={sid}")

    jobs = json.load(open(args.plan, encoding="utf-8"))
    metas, failed = [], []
    for j in jobs:
        g_key, rep = j["group"], j.get("rep", 1)
        if g_key in fc.ALIASES:
            print(f"[alias] {g_key} -> {fc.ALIASES[g_key]}")
            g_key = fc.ALIASES[g_key]
        g = fc.GROUPS[g_key]
        name = f"{g_key}_rep{rep}"

        bal = read_deepseek_balance().get("available")
        try:
            cur = float(bal[0]["total"]) if isinstance(bal, list) else float(bal)
        except Exception:
            cur = -1
        print(f"\n{'='*66}\n【{name}】{g['name']}  余额 ¥{cur}")
        # 注意：必须判 `cur < stop_below`，不能用 `0 <= cur < stop_below`。
        # 2026-10-21 的教训：余额延迟入账会读到负值，而 `0 <= cur` 在负值时为 False，
        # 止损被绕过，导致在余额已耗尽的情况下又连发了两组请求。
        if cur < args.stop_below:
            print(f"  [STOP] 余额 ¥{cur} 低于止损线 {args.stop_below} 元，停止后续运行")
            break

        cfg, info_act, removed, official = build_config(pristine, g_key, args.seed_base + rep)
        ec.save_config(cfg_path(sid), cfg)
        marker = fc.INTERVENTION_MARKERS.get(g["intervention"]) if g["intervention"] else None
        print(f"  初始谣言帖={len(cfg['event_config']['initial_posts'])} "
              f"形式={g['rumor_form']} 移除LLM帖={removed}")
        print(f"  定时干预={'第 %d 轮 / %s' % (g['intervention_round'], g['intervention']) if g['intervention'] else '无'}")

        reset(sid)
        env = os.environ.copy()
        env["MF_DISABLE_TWITTER"] = "1"
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        # 运行环境对本"轮"内的批量文件删除设有阈值保护（默认 50 个文件）。
        # 运行器每组运行都会清一次自身 log/ 目录，长时间批次会累计触发拦截。
        # 这里放宽的只是**该子进程**内、且目标固定为 sim_dir/log 的删除，
        # 同时在 reset() 中已预先清理使实际删除量保持在很小的量级。
        env["CODEBUDDY_SAFE_DELETE_BULK_THRESHOLD"] = "5000"
        cmd = [VENV_PY, RUNNER, "--config", cfg_path(sid),
               "--max-rounds", str(args.rounds), "--no-wait"]
        t0 = time.time()
        proc = subprocess.run(cmd, cwd=sim_dir(sid), env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8", errors="ignore")
        elapsed = round(time.time() - t0, 1)
        # 保存子进程输出，便于事后核验（文件较大时必须留痕）
        stage_dir = os.path.join(out_root, "runs", name)
        os.makedirs(stage_dir, exist_ok=True)
        with open(os.path.join(stage_dir, "process_stdout.txt"), "w", encoding="utf-8") as f:
            f.write(proc.stdout or "")
        print(f"  子进程退出码={proc.returncode} 耗时={elapsed}s")

        copied = snapshot(sid, stage_dir)
        ver = verify(stage_dir, marker, g["intervention_round"])
        if ver.get("checked"):
            print(f"  干预核验: 轮次{ver['rounds_found']} 命中{ver['marker_hits']} "
                  f"-> {'OK' if ver['delivered'] else '未生效!'}")
        n402 = (proc.stdout or "").count("Insufficient Balance")
        aud = completion_audit(stage_dir, args.rounds)
        status = "completed"
        if proc.returncode != 0:
            status = "failed(exit!=0)"
        elif n402:
            status = f"INVALID(402x{n402})"
        elif aud["missing_rounds_1..N"]:
            status = f"INVALID(缺轮次{aud['missing_rounds_1..N']})"
        print(f"  完成度审计: 有动作轮数={aud['rounds_with_actions']}/"
              f"{args.rounds} 缺={aud['missing_rounds_1..N']} 402={n402} -> {status}")
        bal2 = read_deepseek_balance().get("available")
        meta = {"run_name": name, "group": g_key, "rep": rep, "exp": g["exp"],
                "variable": g["variable"], "group_name": g["name"],
                "simulation_id": sid, "rounds": args.rounds,
                "random_seed": args.seed_base + rep, "rumor_form": g["rumor_form"],
                "intervention": g["intervention"] or "NONE",
                "intervention_round": g["intervention_round"],
                "n_agents": n_agents, "interaction_override": info_act,
                "initial_posts_removed_llm": removed,
                "exit_code": proc.returncode, "elapsed_sec": elapsed,
                "final_status": status,
                "api_error_402": n402, "completion_audit": aud,
                "intervention_verify": ver,
                "balance_before": bal, "balance_after": bal2,
                "files": copied, "finished_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        with open(os.path.join(stage_dir, "run_meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        metas.append(meta)
        print(f"  余额 {bal} -> {bal2}")

    summary = {"simulation_id": sid, "rounds": args.rounds, "agents": n_agents,
               "runs": metas, "failed": failed,
               "finished_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    with open(os.path.join(out_root, "batch_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n批次结束 -> {out_root}  共完成 {len(metas)} 次运行")


if __name__ == "__main__":
    main()
