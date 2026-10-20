#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A/B 治理对照实验编排（真实运行，无虚构数据）

设计要点（对照有效性）：
  - 两个实验组共用**同一批 Agent、同一张社交网络、同一份 Seed、同一套时间参数**，
    唯一差异 = 初始帖子中是否含官方辟谣帖。
  - 为此只做一次昂贵的 prepare（本体 / Zep 图谱 / Agent 画像生成），
    之后对同一 simulation_id 反复 start（先 stop + close-env）。
  - 每次 start 前重新覆写 simulation_config.json，确保配置不被回写覆盖。

用法：
  python run_experiments.py --rounds 8 --groups A,B
  python run_experiments.py --prepare-only   # 只做建图/画像，不跑仿真

前提：MiroFish 后端已常驻 http://127.0.0.1:5001
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
import wait_and_snapshot
from run_simulation import read_deepseek_balance

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEED_DIR = os.path.join(REPO, "mirofish", "seed")
RESULTS_DIR = os.path.join(REPO, "mirofish", "results")
BACKEND_UPLOADS = os.path.join(
    os.path.expanduser("~"), "Desktop", "MiroFish", "backend", "uploads", "simulations"
)

SEED_MAIN = "seed_main_baihaitun.md"

REQUIREMENT = (
    "在社交平台仿真环境中推演涉台风\"白海豚\"AI 造假灾情信息的传播。"
    "必须生成多种类型的普通公众 Agent，包括：易信谣并转发的网民、"
    "主动求证的用户、质疑谣言的用户、自媒体与营销号、一线亲历者、"
    "社区长辈、青年学生，以及政务/警方/媒体等机构账号。"
    "Agent 类型要尽量丰富，覆盖不同立场与活跃度，以便观察到真实的转发、"
    "评论与点赞等互动行为。"
)

GROUPS = {
    "A": {"name": "无官方干预（基线）", "official_debunk": False},
    "B": {"name": "早期官方辟谣", "official_debunk": True},
}


def sim_dir(sim_id: str) -> str:
    return os.path.join(BACKEND_UPLOADS, sim_id)


def config_path(sim_id: str) -> str:
    return os.path.join(sim_dir(sim_id), "simulation_config.json")


def stop_and_close(sim_id: str) -> None:
    """停止并关闭上一次运行残留的环境（失败可忽略）。"""
    for path, payload in (("/api/simulation/stop", {"simulation_id": sim_id}),
                          ("/api/simulation/close-env", {"simulation_id": sim_id})):
        try:
            mc._req("POST", path, payload, timeout=60)
            print(f"    {path} -> ok")
        except Exception as e:
            print(f"    {path} -> 忽略: {str(e)[:80]}")


# 每个平台运行会向这些文件"追加"而非截断；DB 也会保留上一组的所有帖子。
# 若不清理，第二组会继承第一组的全部内容与动作日志 → 组间不可比。
RESET_TARGETS = [
    "twitter_simulation.db",
    "reddit_simulation.db",
    "twitter/actions.jsonl",
    "reddit/actions.jsonl",
    "simulation.log",
]


def reset_run_state(sim_id: str) -> None:
    """清空上一组的运行产物，保证本组从干净环境开始。"""
    src = sim_dir(sim_id)
    removed = []
    for rel in RESET_TARGETS:
        p = os.path.join(src, rel)
        if os.path.exists(p):
            try:
                os.remove(p)
                removed.append(rel)
            except Exception as e:
                print(f"    [WARN] 无法删除 {rel}: {str(e)[:80]}")
    # 清理残留的运行状态记录，避免使用上一组的 completed 状态
    for rel in ("run_state.json", "env_status.json"):
        p = os.path.join(src, rel)
        if os.path.exists(p):
            try:
                os.remove(p)
                removed.append(rel)
            except Exception:
                pass
    print(f"    已清理: {removed}")


def snapshot_run(sim_id: str, group: str, out_dir: str) -> dict:
    """把本次运行的真实产物复制到结果目录（本地文件，最完整）。"""
    src = sim_dir(sim_id)
    os.makedirs(out_dir, exist_ok=True)
    copied = {}
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
    # 同时保留 API 侧导出（库表内容）
    try:
        data = mc.export_simulation(sim_id)
        with open(os.path.join(out_dir, "api_export.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        copied["api_export.json"] = os.path.getsize(os.path.join(out_dir, "api_export.json"))
    except Exception as e:
        print(f"    [WARN] API 导出失败: {str(e)[:120]}")
    return copied


def run_group(sim_id: str, group: str, rounds: int, pristine: dict, out_root: str) -> dict:
    g = GROUPS[group]
    print(f"\n{'='*62}")
    print(f"【实验组 {group}】{g['name']}  rounds={rounds}")
    print("=" * 62)

    bal_before = read_deepseek_balance()

    # 1) 从原始配置重建，确保两组起点一致
    cfg = json.loads(json.dumps(pristine))
    info_act = ec.enable_interaction(cfg)
    info_posts = ec.set_initial_posts(cfg, include_official_debunk=g["official_debunk"])
    ec.save_config(config_path(sim_id), cfg)
    print(f"    活跃度覆写: Agent 总数={info_act['agents_total']}, "
          f"每轮激活={info_act['agents_per_round']}, activity_level={info_act['activity_level']}")
    print(f"    初始帖子: {info_posts['rumor_posts']} 条谣言 + "
          f"{'1 条官方辟谣' if info_posts['official_debunk_included'] else '0 条官方干预'}"
          f"（移除 LLM 生成帖 {info_posts['removed_llm_generated_posts']} 条）")

    # 2) 停止环境 + 清空上一组产物（关键：否则会继承上一组的帖子与动作日志）
    stop_and_close(sim_id)
    reset_run_state(sim_id)
    mc.start_simulation(sim_id, max_rounds=rounds)

    # 3) 等待完成：/run-status 会残留上一组 completed 状态，必须改为监测磁盘产物
    ok = wait_and_snapshot.wait_complete(sim_dir(sim_id), timeout=2400)
    final = "completed(file-watch)" if ok else "timeout"
    print(f"    运行状态: {final}")

    # 4) 快照产物
    out_dir = os.path.join(out_root, group)
    copied = snapshot_run(sim_id, group, out_dir)

    bal_after = read_deepseek_balance()
    meta = {
        "group": group,
        "group_name": g["name"],
        "simulation_id": sim_id,
        "rounds": rounds,
        "official_debunk_included": g["official_debunk"],
        "final_status": final,
        "interaction_override": info_act,
        "initial_posts": info_posts,
        "balance_before": bal_before.get("available"),
        "balance_after": bal_after.get("available"),
        "files": copied,
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(out_dir, "run_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"    余额: {bal_before.get('available')} -> {bal_after.get('available')}")
    return meta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--groups", default="A,B")
    ap.add_argument("--simulation-id", default=None, help="复用已 prepare 的仿真（跳过建图）")
    ap.add_argument("--out-root", default=None, help="指定结果根目录（便于与已有组合并）")
    ap.add_argument("--prepare-only", action="store_true")
    args = ap.parse_args()

    print("[0] 健康检查...", end=" ")
    print(mc.health())
    bal_start = read_deepseek_balance()
    print(f"    起始余额: {bal_start.get('available')}")

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_root = args.out_root or os.path.join(RESULTS_DIR, f"exp_ab_{stamp}")
    os.makedirs(out_root, exist_ok=True)

    sim_id = args.simulation_id
    if not sim_id:
        seed_path = os.path.join(SEED_DIR, SEED_MAIN)
        print(f"[1] 上传完整种子 {SEED_MAIN} ...")
        r = mc._req("POST", "/api/graph/ontology/generate",
                    form={"simulation_requirement": REQUIREMENT,
                          "project_name": "exp_ab_governance"},
                    files={"main": (SEED_MAIN, open(seed_path, "rb").read())},
                    timeout=600)
        if not r.get("success"):
            raise RuntimeError(f"ontology/generate 失败: {r}")
        project_id = r["data"]["project_id"]
        onto = r["data"].get("ontology", {})
        print(f"    project_id={project_id} 实体类型={len(onto.get('entity_types', []))} "
              f"文本长度={r['data'].get('total_text_length')}")
        with open(os.path.join(out_root, "1_ontology.json"), "w", encoding="utf-8") as f:
            json.dump(r["data"], f, ensure_ascii=False, indent=2)

        print("[2] 构建知识图谱（Zep）...")
        graph_id = mc.build_graph(project_id)
        print(f"    graph_id={graph_id}")

        print("[3] 创建仿真...")
        sim_id = mc.create_simulation(project_id)
        print(f"    simulation_id={sim_id}")

        print("[4] 准备（生成 Agent 画像与配置，可能耗时较久）...")
        mc.prepare_simulation(sim_id, parallel_profile_count=5)

    pristine = ec.load_config(config_path(sim_id))
    with open(os.path.join(out_root, "0_pristine_config.json"), "w", encoding="utf-8") as f:
        json.dump(pristine, f, ensure_ascii=False, indent=2)
    n_agents = len(pristine.get("agent_configs") or [])
    print(f"\n[5] 已准备完成：Agent 数 = {n_agents}，simulation_id = {sim_id}")
    with open(os.path.join(out_root, "simulation_id.txt"), "w", encoding="utf-8") as f:
        f.write(sim_id)

    if args.prepare_only:
        print("--prepare-only：已停止在准备阶段，未跑仿真")
        return

    metas = []
    for g in [x.strip() for x in args.groups.split(",") if x.strip()]:
        metas.append(run_group(sim_id, g, args.rounds, pristine, out_root))

    bal_end = read_deepseek_balance()
    summary = {
        "simulation_id": sim_id,
        "rounds": args.rounds,
        "agents": n_agents,
        "groups": metas,
        "balance_start": bal_start.get("available"),
        "balance_end": bal_end.get("available"),
        "seed": SEED_MAIN,
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(out_root, "experiment_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n全部完成 -> {out_root}")
    print(f"总费用: {bal_start.get('available')} -> {bal_end.get('available')}")


if __name__ == "__main__":
    main()
