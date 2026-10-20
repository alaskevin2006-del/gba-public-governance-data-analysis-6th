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


def run(exp_key, inject_hour=None, dry=False):
    cfg = EXPERIMENTS[exp_key]
    t0 = time.time()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(RESULTS_DIR, f"{cfg['name']}_{stamp}")
    os.makedirs(out_dir, exist_ok=True)

    print(f"[0] 健康检查...", end=" ")
    print(mc.health())

    # 种子文件选择
    seed_files = {"seed": ("seed_main_baihaitun.md",
                           open(os.path.join(SEED_DIR, "seed_main_baihaitun.md"), "rb").read())}
    req = cfg["requirement"]
    if exp_key == "3A":
        seed_files["inject"] = ("inject_scenario_A_公文辟谣.md",
                                open(os.path.join(SEED_DIR, "inject_scenario_A_公文辟谣.md"), "rb").read())
    elif exp_key == "3B":
        seed_files["inject"] = ("inject_scenario_B_数智实证.md",
                                open(os.path.join(SEED_DIR, "inject_scenario_B_数智实证.md"), "rb").read())
    elif exp_key == "2" and inject_hour:
        # 1 轮 ≈ 2 小时 → 注入轮 = ceil(hour/2)
        inject_round = max(1, -(-inject_hour // 2))
        req += f" 政务辟谣通报必须在第 {inject_round} 轮发布（对应谣言发生后约 {inject_hour} 小时）。"

    if dry:
        print("[dry-run] 配置就绪，未调用后端（需 API Key）")
        print(json.dumps({"exp": exp_key, "requirement": req, "rounds": cfg["rounds"]},
                         ensure_ascii=False, indent=2))
        return

    print("[1] 上传种子 + 生成本体...")
    project_id = mc.upload_and_generate_ontology(seed_files, req, cfg["name"])
    print(f"    project_id={project_id}")

    print("[2] 构建知识图谱（Zep）...")
    graph_id = mc.build_graph(project_id)
    print(f"    graph_id={graph_id}")

    print("[3] 创建仿真...")
    sim_id = mc.create_simulation(project_id, enable_twitter=True, enable_reddit=True)
    print(f"    simulation_id={sim_id}")

    print("[4] 准备（LLM 生成 Agent 画像与配置，耗时 5-15 分钟）...")
    mc.prepare_simulation(sim_id)

    print("[5] 启动仿真 max_rounds=%d ..." % cfg["rounds"])
    mc.start_simulation(sim_id, max_rounds=cfg["rounds"])

    print("[6] 等待完成...")
    final = mc.wait_simulation(sim_id)

    print("[7] 导出数据...")
    data = mc.export_simulation(sim_id)
    data["_meta"] = {
        "exp": exp_key, "project_id": project_id, "graph_id": graph_id,
        "simulation_id": sim_id, "max_rounds": cfg["rounds"],
        "final_status": final, "elapsed_sec": round(time.time() - t0, 1),
        "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(out_dir, "raw_export.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"完成：{out_dir}（状态 {final}）")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", required=True, help="1 / 2 / 3A / 3B")
    ap.add_argument("--inject-hour", type=int, default=None, help="实验二介入小时 1/4/12")
    ap.add_argument("--smoke", action="store_true", help="烟雾测试（8 轮）")
    ap.add_argument("--dry", action="store_true", help="只打印配置，不调用后端")
    a = ap.parse_args()
    if a.smoke:
        EXPERIMENTS["1"]["rounds"] = 8
        run("1", dry=a.dry)
    else:
        run(a.exp, inject_hour=a.inject_hour, dry=a.dry)
