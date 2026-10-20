#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
导出已完成的 MiroFish 仿真结果（不必重跑，零额外 LLM 费用）。

用途：
  当仿真实际已跑完（或轮询脚本被中断）后，按 simulation_id 拉取全部可分析数据，
  并写入 mirofish/results/<name>/raw_export.json。

用法：
  python export_results.py --simulation-id sim_xxxx --name smoke_test
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mirofish_client as mc
from run_simulation import read_deepseek_balance

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS_DIR = os.path.join(REPO, "mirofish", "results")

# 可导出的所有结果端点（基于 @7657031 源码核对）
ENDPOINTS = [
    ("posts", "/posts?platform=twitter&page={p}&per_page=200"),
    ("comments", "/comments?platform=twitter&page={p}&per_page=200"),
    ("reddit_posts", "/posts?platform=reddit&page={p}&per_page=200"),
    ("reddit_comments", "/comments?platform=reddit&page={p}&per_page=200"),
]


def fetch_paged(sim_id, path_tpl, max_pages=20):
    """按页拉取，直到返回不足一页或达到上限。"""
    items = []
    for page in range(1, max_pages + 1):
        r = mc._req("GET", f"/api/simulation/{sim_id}{path_tpl.format(p=page)}")
        d = r.get("data") or {}
        batch = d.get("posts") or d.get("comments") or d.get("items") or []
        if not batch:
            break
        items.extend(batch)
        if len(batch) < 200:
            break
    return items


def export(sim_id, name):
    out_dir = os.path.join(RESULTS_DIR, name)
    os.makedirs(out_dir, exist_ok=True)

    print(f"[1] run-status ...")
    status = mc._req("GET", f"/api/simulation/{sim_id}/run-status").get("data", {})

    print("[2] 抓取各端点 ...")
    data = {}
    for key, tpl in ENDPOINTS:
        try:
            data[key] = fetch_paged(sim_id, tpl)
            print(f"    {key}: {len(data[key])} 条")
        except Exception as e:
            data[key] = []
            print(f"    {key}: 拉取失败 {str(e)[:120]}")

    for single_key, path in (("simulation", f"/api/simulation/{sim_id}"),
                             ("timeline", f"/api/simulation/{sim_id}/timeline"),
                             ("agent_stats", f"/api/simulation/{sim_id}/agent-stats"),
                             ("profiles", f"/api/simulation/{sim_id}/profiles?platform=twitter"),
                             ("reddit_profiles", f"/api/simulation/{sim_id}/profiles?platform=reddit")):
        try:
            data[single_key] = mc._req("GET", path).get("data")
            n = len(data[single_key]) if isinstance(data[single_key], list) else "object"
            print(f"    {single_key}: {n}")
        except Exception as e:
            data[single_key] = None
            print(f"    {single_key}: 失败 {str(e)[:120]}")

    bal = read_deepseek_balance()
    data["_meta"] = {
        "simulation_id": sim_id,
        "export_name": name,
        "run_status": status,
        "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "deepseek_balance": bal.get("available"),
    }

    out_path = os.path.join(out_dir, "raw_export.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"\n已导出 -> {out_path}  ({size_kb:.1f} KB)")
    return out_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--simulation-id", required=True)
    ap.add_argument("--name", default="exported_run")
    a = ap.parse_args()
    export(a.simulation_id, a.name)
