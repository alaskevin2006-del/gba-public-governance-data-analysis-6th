"""
MiroFish 仿真运行入口（烟雾测试 / 正式实验通用）
用法：
  python run_simulation.py --smoke                      # 20-agent 级别种子 × 8 轮校准
  python run_simulation.py --exp 1                      # 实验一：基准扩散（无干预）
  python run_simulation.py --exp 2 --inject-hour 4      # 实验二：第 4 小时介入（1轮=2h → 第2轮注入）
  python run_simulation.py --exp 3 --form A|B           # 实验三：辟谣形态
前提：
  1. MiroFish/.env 已配置 LLM_API_KEY + ZEP_API_KEY
  2. 后端已启动：cd MiroFish && npm run backend（:5001）
注意：
  - MiroFish 的 Agent 数量由图谱实体数决定（LLM 生成），无法直接设定；
    烟雾测试以 max_rounds=8 控制消耗。
  - 实验二的时点注入：MiroFish 原生不支持轮中注入，采用「提前终止 + 二段运行」
    或在 simulation_requirement 中声明注入轮次（近似方案），结果记录中如实标注。
"""
import argparse
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mirofish_client as mc

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SEED_DIR = os.path.join(REPO, "mirofish", "seed")
RESULTS_DIR = os.path.join(REPO, "mirofish", "results")

REQUIREMENT_BASE = (
    "在社交平台仿真环境中推演涉台风\"白海豚\"AI 造假灾情信息的传播："
    "请生成覆盖社区长辈、青年学生、自媒体造谣者、营销号、辟谣意见领袖、政务账号、一线亲历者的 Agent，"
    "观察谣言信息的转发、评论与情绪扩散，输出逐轮的传播量与公众立场变化。"
)

EXPERIMENTS = {
    "1": {"name": "exp1_baseline", "rounds": 15, "inject": None,
          "requirement": REQUIREMENT_BASE + " 本组为无政务干预的基准组，全程不注入任何官方辟谣信息。"},
    "2": {"name": "exp2_golden_window", "rounds": 15, "inject": "by-hour",
          "requirement": REQUIREMENT_BASE + " 本组在模拟中期由政务账号 Agent 发布官方辟谣通报（具体轮次见附加材料）。"},
    "3A": {"name": "exp3_form_A", "rounds": 15, "inject": "scenario_A",
           "requirement": REQUIREMENT_BASE + " 本组在第 2 轮由政务账号发布传统公文式辟谣（见附加材料 inject_scenario_A）。"},
    "3B": {"name": "exp3_form_B", "rounds": 15, "inject": "scenario_B",
           "requirement": REQUIREMENT_BASE + " 本组在第 2 轮由政务账号发布数智实证型辟谣（见附加材料 inject_scenario_B）。"},
}


def read_deepseek_balance(env_path=None):
    """读取 DeepSeek 账户余额（用于核算本次运行真实费用）。

    返回 dict：{"ok":bool, "used":float, "available":list, "error":str}
    注意：余额为**账户累计口径**，单次运行费用 = 运行后 used - 运行前 used。
    """
    try:
        cfg = {}
        p = env_path or str(
            os.path.join(os.path.expanduser("~"), "Desktop", "MiroFish", ".env")
        )
        if os.path.exists(p):
            for line in open(p, encoding="utf-8").read().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = v.strip()
        key = cfg.get("LLM_API_KEY")
        base = (cfg.get("LLM_BASE_URL") or "https://api.deepseek.com").rstrip("/")
        if not key:
            return {"ok": False, "error": "未读到 LLM_API_KEY"}
        req = urllib.request.Request(
            f"{base}/user/balance",
            headers={"Authorization": f"Bearer {key}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            b = json.loads(r.read().decode("utf-8"))
        avail = []
        for item in b.get("balance_infos", []) or []:
            avail.append(
                {
                    "currency": item.get("currency"),
                    "total": item.get("total_balance"),
                    "granted": item.get("granted_balance"),
                    "topped_up": item.get("topped_up_balance"),
                }
            )
        return {"ok": True, "raw": b, "available": avail}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def run(seed_name, project_name, requirement, rounds, dry=False):
    t0 = time.time()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(RESULTS_DIR, f"{project_name}_{stamp}")
    os.makedirs(out_dir, exist_ok=True)

    print("[0] 健康检查...", end=" ")
    print(mc.health())

    bal_before = read_deepseek_balance()
    if bal_before.get("ok"):
        print(f"    运行前 DeepSeek 余额: {bal_before['available']}")
    else:
        print(f"    [WARN] 读取余额失败: {bal_before.get('error')}")

    seed_files = {
        "main": (seed_name, open(os.path.join(SEED_DIR, seed_name), "rb").read())
    }

    if dry:
        print("[dry-run] 配置就绪，未调用后端")
        print(json.dumps({"seed": seed_name, "requirement": requirement,
                          "rounds": rounds}, ensure_ascii=False, indent=2))
        return

    print("[1] 上传种子 + 生成本体...")
    r = mc._req("POST", "/api/graph/ontology/generate",
                form={"simulation_requirement": requirement,
                      "project_name": project_name},
                files=seed_files, timeout=300)
    if not r.get("success"):
        raise RuntimeError(f"ontology/generate 失败: {r}")
    project_id = r["data"]["project_id"]
    onto = r["data"].get("ontology", {})
    print(f"    project_id={project_id}")
    print(f"    实体类型 {len(onto.get('entity_types', []))} 个 / "
          f"关系类型 {len(onto.get('edge_types', []))} 个 / "
          f"文本长度 {r['data'].get('total_text_length')}")

    with open(os.path.join(out_dir, "1_ontology.json"), "w", encoding="utf-8") as f:
        json.dump(r["data"], f, ensure_ascii=False, indent=2)

    print("[2] 构建知识图谱（Zep，耗时数分钟）...")
    graph_id = mc.build_graph(project_id)
    print(f"    graph_id={graph_id}")

    print("[3] 创建仿真...")
    sim_id = mc.create_simulation(project_id, enable_twitter=True, enable_reddit=True)
    print(f"    simulation_id={sim_id}")

    print("[4] 准备（LLM 生成 Agent 画像与配置，耗时可能 5-15 分钟）...")
    mc.prepare_simulation(sim_id, parallel_profile_count=2)

    print(f"[5] 启动仿真 max_rounds={rounds} ...")
    mc.start_simulation(sim_id, max_rounds=rounds)

    print("[6] 等待完成...")
    final = mc.wait_simulation(sim_id, poll=20)

    bal_after = read_deepseek_balance()
    print("[7] 导出数据...")
    data = mc.export_simulation(sim_id)
    data["_meta"] = {
        "project_name": project_name, "seed": seed_name,
        "project_id": project_id, "graph_id": graph_id,
        "simulation_id": sim_id, "max_rounds": rounds,
        "final_status": final, "elapsed_sec": round(time.time() - t0, 1),
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "balance_before": bal_before.get("available"),
        "balance_after": bal_after.get("available"),
    }
    with open(os.path.join(out_dir, "raw_export.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"完成：{out_dir}（状态 {final}，用时 {data['_meta']['elapsed_sec']}s）")
    print(f"运行后 DeepSeek 余额: {bal_after.get('available')}")
    return out_dir


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true",
                    help="最小烟雾测试：微种子 seed_smoke_min.md × 2 轮（低成本）")
    ap.add_argument("--exp", choices=["1", "2", "3A", "3B"],
                    help="正式实验组（本次不执行）")
    ap.add_argument("--inject-hour", type=int, default=None)
    ap.add_argument("--rounds", type=int, default=None, help="覆盖默认轮数")
    ap.add_argument("--dry", action="store_true", help="只打印配置，不调用后端")
    a = ap.parse_args()

    if a.smoke:
        run(seed_name="seed_smoke_min.md", project_name="smoke_test",
            requirement=REQUIREMENT_BASE + EXPERIMENTS["1"]["requirement"][len(REQUIREMENT_BASE):],
            rounds=a.rounds or 2, dry=a.dry)
    elif a.exp:
        cfg = EXPERIMENTS[a.exp]
        req = cfg["requirement"]
        if a.exp == "2" and a.inject_hour:
            inject_round = max(1, -(-a.inject_hour // 2))
            req += f" 政务辟谣通报必须在第 {inject_round} 轮发布（对应谣言发生后约 {a.inject_hour} 小时）。"
        seed_map = {"3A": "inject_scenario_A_公文辟谣.md", "3B": "inject_scenario_B_数智实证.md"}
        extra = seed_map.get(a.exp)
        run(seed_name="seed_main_baihaitun.md", project_name=cfg["name"],
            requirement=req, rounds=a.rounds or cfg["rounds"], dry=a.dry)
    else:
        ap.error("需指定 --smoke 或 --exp")
