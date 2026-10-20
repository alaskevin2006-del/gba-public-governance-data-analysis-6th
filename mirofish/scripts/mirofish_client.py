"""
MiroFish 后端 API 客户端（基于源码 @7657031 的真实接口）
依赖：MiroFish/.env 已配置 LLM_API_KEY + ZEP_API_KEY，后端已启动于 http://localhost:5001
"""
import json
import time
import urllib.request
import urllib.error
import uuid

BASE = "http://127.0.0.1:5001"

# MiroFish 是本机服务：必须显式绕过系统代理/沙箱代理，
# 否则 urllib 会把 127.0.0.1 请求也发给代理，返回 HTTP 502 upstream connect failed。
_NO_PROXY_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _req(method, path, payload=None, form=None, files=None, timeout=120):
    """发送请求。form/files 为 multipart；payload 为 JSON。返回解析后的 JSON。

    注意（@7657031 源码核实）：后端用 `request.files.getlist('files')` 读取，
    因此**每个文件都必须使用同一个字段名 "files"**，不能用自定义 key。
    """
    url = f"{BASE}{path}"
    boundary = uuid.uuid4().hex
    data = None
    headers = {}

    if files or form:
        parts = []
        for k, v in (form or {}).items():
            parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode("utf-8")
            )
        # files: {任意内部 key: (filename, bytes)}，但 multipart 字段名统一标记为 "files"
        for fname, content in (files or {}).values():
            parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"{fname}\"\r\n"
                f"Content-Type: text/markdown\r\n\r\n".encode("utf-8") + content + b"\r\n"
            )
        parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        data = b"".join(parts)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        # 本机服务必须绕过系统/沙箱代理，否则 localhost 请求会被代理拒绝（HTTP 502）
        with _NO_PROXY_OPENER.open(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {path}: {body[:500]}") from e


def health():
    return _req("GET", "/health", timeout=10)


def upload_and_generate_ontology(files, simulation_requirement, project_name):
    """POST /api/graph/ontology/generate（multipart）
    files: {name: (filename, bytes)}；返回 project_id"""
    r = _req("POST", "/api/graph/ontology/generate",
             form={"simulation_requirement": simulation_requirement,
                   "project_name": project_name},
             files=files, timeout=300)
    if not r.get("success"):
        raise RuntimeError(f"ontology/generate 失败: {r}")
    return r["data"]["project_id"]


def build_graph(project_id):
    """POST /api/graph/build → 轮询 task → 返回 graph_id"""
    r = _req("POST", "/api/graph/build", {"project_id": project_id})
    if not r.get("success"):
        raise RuntimeError(f"graph/build 失败: {r}")
    task_id = r["data"]["task_id"]
    while True:
        t = _req("GET", f"/api/graph/task/{task_id}")
        d = t.get("data", {})
        status = d.get("status")
        print(f"  [graph] {status} {d.get('progress', '')} {d.get('message', '')[:60]}")
        if status == "completed":
            return d.get("graph_id") or d.get("result", {}).get("graph_id")
        if status in ("failed", "error"):
            raise RuntimeError(f"图谱构建失败: {d}")
        time.sleep(10)


def create_simulation(project_id, enable_twitter=True, enable_reddit=True):
    r = _req("POST", "/api/simulation/create",
             {"project_id": project_id, "enable_twitter": enable_twitter,
              "enable_reddit": enable_reddit})
    if not r.get("success"):
        raise RuntimeError(f"simulation/create 失败: {r}")
    return r["data"]["simulation_id"]


def prepare_simulation(simulation_id, parallel_profile_count=5):
    """POST /api/simulation/prepare → 轮询 prepare/status（LLM 生成画像与配置，耗时）"""
    r = _req("POST", "/api/simulation/prepare",
             {"simulation_id": simulation_id,
              "use_llm_for_profiles": True,
              "parallel_profile_count": parallel_profile_count})
    if not r.get("success"):
        raise RuntimeError(f"prepare 失败: {r}")
    if r["data"].get("status") == "ready":
        return
    task_id = r["data"].get("task_id")
    while True:
        t = _req("POST", "/api/simulation/prepare/status",
                 {"task_id": task_id, "simulation_id": simulation_id})
        d = t.get("data", {})
        print(f"  [prepare] {d.get('status')} {d.get('progress', '')}% {str(d.get('message', ''))[:60]}")
        if d.get("status") in ("completed", "ready"):
            return
        if d.get("status") in ("failed", "error"):
            raise RuntimeError(f"prepare 失败: {d}")
        time.sleep(15)


def start_simulation(simulation_id, max_rounds=8, platform="parallel"):
    r = _req("POST", "/api/simulation/start",
             {"simulation_id": simulation_id, "platform": platform,
              "max_rounds": max_rounds})
    if not r.get("success"):
        raise RuntimeError(f"start 失败: {r}")
    return r["data"]


def wait_simulation(simulation_id, poll=30, max_wait=5400):
    """轮询 run-status 直到完成/失败/停止。

    重要（2026-10-20 真实运行发现）：MiroFish @7657031 存在**状态同步滞后** ——
    两平台均已 completed、progress=100% 时，`runner_status` 仍可能长期停留在 "running"。
    因此判定完成必须同时满足以下任一：
      1. runner_status ∈ {completed, failed, stopped}
      2. 两个已启用平台均 completed（twitter_completed 且 reddit_completed）
    否则会空转到超时，不产生新费用但浪费时间。
    """
    start = time.time()
    last_round = None
    while True:
        r = _req("GET", f"/api/simulation/{simulation_id}/run-status")
        d = r.get("data", {})
        status = d.get("runner_status")
        cur = d.get("current_round")
        tw_done = d.get("twitter_completed")
        rd_done = d.get("reddit_completed")
        prog = d.get("progress_percent")

        if cur != last_round:
            print(f"  [run] status={status} round={cur} progress={prog}% "
                  f"tw={tw_done} rd={rd_done} actions={d.get('total_actions_count')}")
            last_round = cur

        # 条件 1：上游最终状态
        if status in ("completed", "failed", "stopped"):
            return status
        # 条件 2：双平台完成且进度 100%（规避 runner_status 滞后）
        if tw_done and rd_done and prog is not None and float(prog) >= 100.0:
            print("  [run] 双平台均已完成且 progress=100%，判定结束"
                  "（runner_status 滞后为上游已知现象）")
            return "completed_platforms"
        if time.time() - start > max_wait:
            print(f"  [run] 等待超过 {max_wait}s，提前返回（请人工核查后端日志）")
            return "timeout"

        time.sleep(poll)


def export_simulation(simulation_id):
    """导出全部可分析数据"""
    out = {}
    out["simulation"] = _req("GET", f"/api/simulation/{simulation_id}").get("data")
    out["timeline"] = _req("GET", f"/api/simulation/{simulation_id}/timeline").get("data")
    out["agent_stats"] = _req("GET", f"/api/simulation/{simulation_id}/agent-stats").get("data")
    out["posts"] = []
    out["comments"] = []
    # posts/comments 支持分页，逐页拉取
    for path, key in ((f"/api/simulation/{simulation_id}/posts", "posts"),
                      (f"/api/simulation/{simulation_id}/comments", "comments")):
        page = 1
        while True:
            r = _req("GET", f"{path}?page={page}&per_page=1000")
            d = r.get("data") or {}
            items = d.get(key) or d.get("items") or []
            out[key].extend(items)
            if len(items) < 1000 or page >= 50:
                break
            page += 1
    return out
