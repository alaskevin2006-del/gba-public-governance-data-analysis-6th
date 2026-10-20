#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
正式实验编排（三组反事实实验，真实运行）

用法示例：
  # 只跑一次 plan.json 中的全部条件
  python run_formal_experiments.py --rounds 16 --plan plan_rep1.json --simulation-id sim_xxx
  # 指定条件串
  python run_formal_experiments.py --rounds 16 --groups E1A,E1B --simulation-id sim_xxx

关键控制（对照有效性）：
  · 只 prepare 一次 → 所有组共用同一批 Agent、同一张社交网络、同一份 Seed。
  · 每组运行前从 pristine_config 重建配置 + stop/close-env + 删除上一组产物。
  · 活跃度闸门（enable_interaction）对所有组完全一致。
  · 每组仅改变 plan 中声明的目标变量。
  · random_seed 逐次递增（仅 Python 侧可复现，LLM 采样本身仍随机 → 需要重复实验）。
"""
import argparse
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mirofish_client as mc
import experiment_config as ec
import formal_experiment_config as fc
import wait_and_snapshot
from run_simulation import read_deepseek_balance

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS_DIR = os.path.join(REPO, "mirofish", "results")
BACKEND_UPLOADS = os.path.join(
    os.path.expanduser("~"), "Desktop", "MiroFish", "backend", "uploads", "simulations"
)


def sim_dir(sid):
    return os.path.join(BACKEND_UPLOADS, sid)


def config_path(sid):
    return os.path.join(sim_dir(sid), "simulation_config.json")


def stop_and_close(sid):
    for path, payload in (("/api/simulation/stop", {"simulation_id": sid}),
                          ("/api/simulation/close-env", {"simulation_id": sid})):
        try:
            mc._req("POST", path, payload, timeout=60)
        except Exception:
            pass


RESET_TARGETS = [
    "twitter_simulation.db", "reddit_simulation.db",
    "twitter/actions.jsonl", "reddit/actions.jsonl", "simulation.log",
    "run_state.json", "env_status.json",
]


def reset_run_state(sid):
    removed = []
    for rel in RESET_TARGETS:
        p = os.path.join(sim_dir(sid), rel)
        if os.path.exists(p):
            try:
                os.remove(p)
                removed.append(rel)
            except Exception:
                pass
    return removed


def verify_intervention(out_dir, marker, expect_round):
    """核验干预内容是否真的出现在指定轮次（或至少出现在日志中）。返回核验结论。"""
    if not marker:
        return {"checked": False, "reason": "本组为无干预条件"}
    found_rounds = set()
    total_hits = 0
    for plat in ("twitter_actions.jsonl", "reddit_actions.jsonl"):
        p = os.path.join(out_dir, plat)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if marker in json.dumps(d, ensure_ascii=False):
                    total_hits += 1
                    r = d.get("round")
                    if r is not None:
                        found_rounds.add(int(r))
    rounds = sorted(found_rounds)
    return {
        "checked": True,
        "marker_hits": total_hits,
        "rounds_found": rounds,
        "expected_round": expect_round,
        "first_round": rounds[0] if rounds else None,
        "delivered": bool(rounds),
        "on_time": (bool(rounds) and expect_round is not None and rounds[0] == expect_round),
    }


def snapshot_run(sid, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    copied = {}
    src = sim_dir(sid)
    for rel, fname in (
        ("simulation_config.json", "simulation_config.json"),
        ("simulation.log", "simulation.log"),
        ("twitter/actions.jsonl", "twitter_actions.jsonl"),
        ("reddit/actions.jsonl", "reddit_actions.jsonl"),
    ):
        s = os.path.join(src, rel)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(out_dir, fname))
            copied[fname] = os.path.getsize(s)
    return copied


def run_one(sid, group_key, rep, rounds, pristine, out_root, seed_base, platform):
    g = fc.GROUPS[group_key]
    run_name = f"{group_key}_rep{rep}"
    print(f"\n{'='*66}")
    print(f"【{run_name}】{g['name']}   rounds={rounds} seed={seed_base + rep}")
    print("=" * 66)

    bal_before = read_deepseek_balance()
    cfg = json.loads(json.dumps(pristine))

    # 1) 活跃度闸门（全组一致）
    info_act = ec.enable_interaction(cfg)

    # 2) 谣言形式（实验一的自变量）
    picked = ec.pick_agents(cfg)
    public, official = picked["public"], picked["official"]
    rumors = fc.rumor_posts(g["rumor_form"])
    posts = []
    for i, content in enumerate(rumors):
        posts.append({"content": content, "poster_agent_id": public[i % len(public)],
                      "tag": f"initial_rumor_{g['rumor_form']}"})
    ec_ev = cfg.setdefault("event_config", {})
    removed = ec_ev.get("initial_posts", [])
    ec_ev["initial_posts"] = posts

    # 3) 干预注入（实验二时点 / 实验三形态）—— 走本工程补齐的 scheduled_events
    events = []
    marker = None
    if g["intervention"]:
        content = fc.INTERVENTION_TEXTS[g["intervention"]]
        marker = fc.INTERVENTION_MARKERS[g["intervention"]]
        events = [{
            "round": g["intervention_round"],
            "agent_id": official[0],
            "content": content,
            "tag": g["intervention"],
        }]
    ec_ev["scheduled_events"] = events

    # 4) 随机种子
    cfg["random_seed"] = seed_base + rep

    ec.save_config(config_path(sid), cfg)
    print(f"    Agent={info_act['agents_total']} 每轮激活={info_act['agents_per_round']} "
          f"activity={info_act['activity_level']}")
    print(f"    初始谣言帖={len(posts)}（形式={g['rumor_form']}，移除 LLM 自定义帖 {len(removed)} 条）")
    print(f"    定时干预={'第 %d 轮 / %s' % (events[0]['round'], events[0]['tag']) if events else '无'}")

    t0 = time.time()
    stop_and_close(sid)
    reset_run_state(sid)
    mc.start_simulation(sid, max_rounds=rounds, platform=platform)
    ok = wait_and_snapshot.wait_complete(sim_dir(sid), timeout=3600)
    elapsed = round(time.time() - t0, 1)
    print(f"    完成判定={'完成' if ok else '超时'}  耗时 {elapsed}s")

    out_dir = os.path.join(out_root, "runs", run_name)
    copied = snapshot_run(sid, out_dir)
    try:
        data = mc.export_simulation(sid)
        with open(os.path.join(out_dir, "api_export.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"    [WARN] API 导出失败: {str(e)[:100]}")

    ver = verify_intervention(out_dir, marker, g["intervention_round"])
    if ver.get("checked"):
        print(f"    干预核验: 出现于轮次 {ver['rounds_found']}（期望 {ver['expected_round']}）"
              f" 命中 {ver['marker_hits']} 次 -> {'OK' if ver['delivered'] else '未生效!'}")

    bal_after = read_deepseek_balance()
    meta = {
        "run_name": run_name,
        "group": group_key,
        "rep": rep,
        "exp": g["exp"],
        "variable": g["variable"],
        "group_name": g["name"],
        "simulation_id": sid,
        "rounds": rounds,
        "random_seed": cfg["random_seed"],
        "rumor_form": g["rumor_form"],
        "intervention": g["intervention"],
        "intervention_round": g["intervention_round"],
        "n_agents": info_act["agents_total"],
        "interaction_override": info_act,
        "initial_posts_removed_llm": len(removed),
        "final_status": "completed(file-watch)" if ok else "timeout",
        "elapsed_sec": elapsed,
        "intervention_verify": ver,
        "balance_before": bal_before.get("available"),
        "balance_after": bal_after.get("available"),
        "files": copied,
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(out_dir, "run_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"    余额 {bal_before.get('available')} -> {bal_after.get('available')}")
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=16)
    ap.add_argument("--simulation-id", required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--groups", default=None, help="逗号分隔，重复次数用 × 表示，如 E1A*2,E1B*2")
    ap.add_argument("--plan", default=None, help="JSON 文件：[{group, rep}, ...]")
    ap.add_argument("--seed-base", type=int, default=20261021)
    ap.add_argument("--platform", default="reddit",
                    help="运行平台：reddit / twitter / parallel（默认 reddit，见文档理由）")
    args = ap.parse_args()

    print("[0] 健康检查...", end=" ")
    print(mc.health())
    bal_start = read_deepseek_balance()
    print(f"    起始余额: {bal_start.get('available')}")

    out_root = args.out_root
    os.makedirs(out_root, exist_ok=True)
    sid = args.simulation_id

    pristine = ec.load_config(config_path(sid))
    pristine_path = os.path.join(out_root, "0_pristine_config.json")
    if not os.path.exists(pristine_path):
        with open(pristine_path, "w", encoding="utf-8") as f:
            json.dump(pristine, f, ensure_ascii=False, indent=2)
    n_agents = len(pristine.get("agent_configs") or [])
    print(f"    Agent 数 = {n_agents}, simulation_id = {sid}")

    # 构造计划
    jobs = []
    if args.plan:
        jobs = json.load(open(args.plan, encoding="utf-8"))
    else:
        for token in args.groups.split(","):
            token = token.strip()
            if not token:
                continue
            if "×" in token or "*" in token:
                sep = "×" if "×" in token else "*"
                key, n = token.split(sep)
                nreps = int(n)
            else:
                key, nreps = token, 1
            key = key.strip()
            if key in fc.ALIASES:
                print(f"    [alias] {key} -> {fc.ALIASES[key]}（同一条件，不重复运行）")
                key = fc.ALIASES[key]
            for r in range(1, nreps + 1):
                jobs.append({"group": key, "rep": r})

    print(f"\n任务队列（共 {len(jobs)} 次运行）:")
    for j in jobs:
        print(f"    {j['group']}  rep{j['rep']}   {fc.GROUPS[j['group']]['name']}")

    metas = []
    failed = []
    for j in jobs:
        try:
            metas.append(run_one(sid, j["group"], j["rep"], args.rounds,
                                 pristine, out_root, args.seed_base, args.platform))
        except Exception as e:
            print(f"    [FAIL] {j} -> {str(e)[:200]}")
            failed.append({**j, "error": str(e)[:300]})
            time.sleep(10)

    bal_end = read_deepseek_balance()
    summary = {
        "simulation_id": sid,
        "rounds": args.rounds,
        "agents": n_agents,
        "seed_base": args.seed_base,
        "platform": args.platform,
        "runs": metas,
        "failed": failed,
        "balance_start": bal_start.get("available"),
        "balance_end": bal_end.get("available"),
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(out_root, "batch_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n批次完成 -> {out_root}")
    print(f"总费用: {bal_start.get('available')} -> {bal_end.get('available')}")
    if failed:
        print(f"失败 {len(failed)} 项: {failed}")


if __name__ == "__main__":
    main()
