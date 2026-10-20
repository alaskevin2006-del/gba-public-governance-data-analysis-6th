"""
MiroFish 后端 API 客户端（基于源码 @7657031 的真实接口）
依赖：MiroFish/.env 已配置 LLM_API_KEY + ZEP_API_KEY，后端已启动于 http://localhost:5001
"""
import json
import time
import urllib.request
import urllib.error
import uuid

BASE = "http://localhost:5001"


def _req(method, path, payload=None, form=None, files=None, timeout=120):
    """发送请求。form/files 为 multipart；payload 为 JSON。返回解析后的 JSON。"""
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
        for k, (fname, content) in (files or {}).items():
            parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{fname}\"\r\n"
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
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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


def wait_simulation(simulation_id, poll=30, idle_limit=120):
    """轮询 run-status 直到 completed/failed/stopped。
    idle_limit: 连续 N 次(秒) 无新轮次也继续等，仅打印心跳。"""
    last_round = None
    while True:
        r = _req("GET", f"/api/simulation/{simulation_id}/run-status")
        d = r.get("data", {})
        status = d.get("runner_status")
        cur = d.get("current_round")
        if cur != last_round:
            print(f"  [run] status={status} round={cur}")
            last_round = cur
        else:
            print(f"  [run] status={status} round={cur} (等待中)")
        if status in ("completed", "failed", "stopped"):
            return status
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
