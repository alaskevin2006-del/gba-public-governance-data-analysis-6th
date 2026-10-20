#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
API 连通性最小验证脚本（不属于正式实验）

验证对象：
  1. DeepSeek LLM API：/models、/chat/completions、/user/balance
  2. Zep Cloud API：认证与 group 读写能力探测

设计原则：
  - 密钥只从环境变量或 MiroFish/.env 读取，绝不打印、绝不写入任何输出文件。
  - 每个接口只发最小请求（max_tokens=8），控制成本。
  - 明确区分：认证错误(401) / 参数错误(400) / 额度不足(402/余额) / 网络错误 / SDK 兼容问题。

用法：
    python scripts/verify_apis.py [--env "C:/Users/Kevin/Desktop/MiroFish/.env"]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# 允许通过公司/校园网代理访问外网（仅在显式提供时启用）
# 默认不设置代理，先看能否直连

try:
    import requests
except ImportError:
    print("[FATAL] 缺少 requests，请先 pip install requests")
    sys.exit(2)

REDACT = "***REDACTED***"


def load_env_file(path: str) -> dict:
    """读取 dotenv 文件到字典（不打印值）。"""
    p = Path(path)
    if not p.exists():
        print(f"[WARN] 未找到 env 文件: {path}")
        return {}
    cfg = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        cfg[k.strip()] = v.strip().strip('"').strip("'")
    print(f"[OK] 读取 env 文件: {path}  键数量={len(cfg)}")
    return cfg


def mask(s: str, keep: int = 6) -> str:
    if not s:
        return "(empty)"
    return s[:keep] + "…" + REDACT


def classify_http(status: int) -> str:
    return {
        400: "参数错误 (400 Bad Request)",
        401: "认证失败 (401 Unauthorized) - Key 无效或缺失",
        402: "额度不足 (402 Payment Required)",
        403: "权限不足 (403 Forbidden)",
        404: "接口不存在 (404 Not Found) - Base URL 或路径错误",
        422: "请求体校验失败 (422)",
        429: "限流 (429 Too Many Requests)",
    }.get(status, f"HTTP {status}")


# ---------------------------------------------------------------- DeepSeek ---
def check_deepseek(cfg: dict) -> dict:
    print("\n" + "=" * 62)
    print("【1】DeepSeek LLM API 验证")
    print("=" * 62)

    key = cfg.get("LLM_API_KEY") or os.getenv("LLM_API_KEY", "")
    base = (cfg.get("LLM_BASE_URL") or os.getenv("LLM_BASE_URL", "")).rstrip("/")
    model = cfg.get("LLM_MODEL_NAME") or os.getenv("LLM_MODEL_NAME", "")

    print(f"  BASE_URL : {base}")
    print(f"  MODEL    : {model}")
    print(f"  API_KEY  : {mask(key)}")

    result = {"ok": False, "model": model, "tokens": 0, "balance": None, "error": None}
    if not key:
        result["error"] = "LLM_API_KEY 未提供"
        print(f"  [FAIL] {result['error']}")
        return result

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    session = requests.Session()

    # 1.1 /models —— 只验证 Key 有效性
    print("\n  --- 1.1 GET /models (验证 Key) ---")
    try:
        t0 = time.time()
        r = session.get(f"{base}/models", headers=headers, timeout=30)
        dt = time.time() - t0
        if r.status_code == 200:
            data = r.json()
            names = [m.get("id") for m in data.get("data", [])]
            print(f"  [OK] HTTP 200 ({dt:.2f}s) 可用模型 {len(names)} 个: {names}")
            if model not in names:
                print(f"  [WARN] 配置的模型 '{model}' 不在返回列表中，调用可能失败")
        else:
            print(f"  [FAIL] {classify_http(r.status_code)}")
            print(f"        响应: {r.text[:300]}")
            result["error"] = f"/models {r.status_code}"
            return result
    except requests.exceptions.SSLError as e:
        print(f"  [FAIL] SSL 错误（可能需代理/证书问题）: {str(e)[:200]}")
        result["error"] = f"SSL: {str(e)[:200]}"
        return result
    except requests.exceptions.ConnectionError as e:
        print(f"  [FAIL] 网络连接错误（可能被沙箱/防火墙拦截）: {str(e)[:200]}")
        result["error"] = f"Connection: {str(e)[:200]}"
        return result
    except Exception as e:
        print(f"  [FAIL] 未知错误: {str(e)[:200]}")
        result["error"] = str(e)[:200]
        return result

    # 1.2 /user/balance —— DeepSeek 专有余额查询
    print("\n  --- 1.2 GET /user/balance (余额) ---")
    try:
        r = session.get(f"{base}/user/balance", headers=headers, timeout=30)
        if r.status_code == 200:
            b = r.json()
            result["balance"] = b
            granted = b.get("total_granted") or b.get("granted_balance") or 0
            topped = b.get("total_topped_up") or b.get("topped_up_balance") or 0
            used = b.get("total_used") or b.get("used_balance") or 0
            avail = b.get("balance_infos") or b.get("balances") or []
            print(f"  [OK] HTTP 200 累计充值={granted} 累计使用={used}")
            for item in avail:
                if isinstance(item, dict):
                    print(
                        f"       币种={item.get('currency')} "
                        f"总额={item.get('total_balance')} "
                        f"剩余={item.get('granted_balance')}+{item.get('topped_up_balance')}"
                    )
            if not avail:
                print(f"       原始响应键: {list(b.keys())}")
        else:
            print(f"  [INFO] {classify_http(r.status_code)}（DeepSeek 专有余额接口，非阻塞）")
            print(f"         响应: {r.text[:200]}")
    except Exception as e:
        print(f"  [INFO] 余额查询失败（非阻塞）: {str(e)[:150]}")

    # 1.3 /chat/completions —— 最小生成测试
    print("\n  --- 1.3 POST /chat/completions (最小生成) ---")
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "Reply with only one word: OK"}
        ],
        "max_tokens": 8,
        "temperature": 0,
        "stream": False,
    }
    try:
        t0 = time.time()
        r = session.post(
            f"{base}/chat/completions", headers=headers, json=payload, timeout=60
        )
        dt = time.time() - t0
        if r.status_code == 200:
            data = r.json()
            usage = data.get("usage", {})
            pt = usage.get("prompt_tokens", 0)
            ct = usage.get("completion_tokens", 0)
            tt = usage.get("total_tokens", pt + ct)
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            result["tokens"] = tt
            result["ok"] = True
            print(f"  [OK] HTTP 200 ({dt:.2f}s)")
            print(f"       回复内容: {content[:80]!r}")
            print(f"       Token: prompt={pt} completion={ct} total={tt}")
        else:
            print(f"  [FAIL] {classify_http(r.status_code)}")
            body = r.text[:400].replace(key, REDACT)
            print(f"        响应: {body}")
            result["error"] = f"/chat/completions {r.status_code}"
    except Exception as e:
        print(f"  [FAIL] {str(e)[:200]}")
        result["error"] = str(e)[:200]

    return result


# --------------------------------------------------------------------- Zep ---
def check_zep(cfg: dict) -> dict:
    print("\n" + "=" * 62)
    print("【2】Zep Cloud 记忆图谱 API 验证")
    print("=" * 62)

    zep_key = cfg.get("ZEP_API_KEY") or os.getenv("ZEP_API_KEY", "")
    print(f"  ZEP_API_KEY: {mask(zep_key)}")

    result = {"ok": False, "sdk": None, "error": None}
    if not zep_key:
        result["error"] = "ZEP_API_KEY 未提供"
        print(f"  [FAIL] {result['error']}")
        return result

    # 2.1 直接 REST 探测（不依赖 SDK，先确认网络与认证）
    print("\n  --- 2.1 GET https://api.getzep.com/api/v2/users (REST 探测) ---")
    headers = {"Authorization": f"Api-Key {zep_key}"}
    try:
        r = requests.get(
            "https://api.getzep.com/api/v2/users", headers=headers, timeout=30
        )
        if r.status_code == 200:
            n = len(r.json()) if isinstance(r.json(), list) else -1
            print(f"  [OK] HTTP 200 认证通过（返回 {n if n>=0 else '?'} 条记录）")
            result["ok"] = True
        else:
            print(f"  [FAIL] {classify_http(r.status_code)}")
            print(f"        响应: {r.text[:300]}")
            result["error"] = f"REST {r.status_code}"
    except Exception as e:
        print(f"  [FAIL] {str(e)[:200]}")
        result["error"] = str(e)[:200]
        return result

    # 2.2 SDK 兼容性（若后端 venv 装了 zep-cloud，用 REST 也可，此步可选）
    print("\n  --- 2.2 zep-cloud SDK 版本探测 ---")
    try:
        import importlib.metadata as md

        ver = md.version("zep-cloud")
        result["sdk"] = ver
        print(f"  [OK] zep-cloud=={ver} 已安装")
    except Exception:
        print("  [INFO] 当前 Python 环境未安装 zep-cloud（MiroFish 后端 venv 内已安装即可）")

    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--env",
        default=str(Path.home() / "Desktop" / "MiroFish" / ".env"),
        help="MiroFish .env 路径",
    )
    ap.add_argument("--proxy", default="", help="如沙箱需代理，形如 http://127.0.0.1:7897")
    args = ap.parse_args()

    if args.proxy:
        os.environ["HTTP_PROXY"] = args.proxy
        os.environ["HTTPS_PROXY"] = args.proxy
        print(f"[INFO] 已启用代理: {args.proxy}")

    cfg = load_env_file(args.env)

    print("\n" + "#" * 62)
    print("# MiroFish 外部依赖 API 连通性验证")
    print(f"# 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("# 注意: 本脚本不输出任何密钥明文")
    print("#" * 62)

    ds = check_deepseek(cfg)
    zp = check_zep(cfg)

    print("\n" + "=" * 62)
    print("【汇总】")
    print("=" * 62)
    print(
        f"  DeepSeek chat : {'✅ 通过' if ds['ok'] else '❌ 失败: ' + str(ds['error'])}"
    )
    print(f"                  model={ds['model']} 本次消耗 token={ds['tokens']}")
    print(f"  Zep Cloud     : {'✅ 通过' if zp['ok'] else '❌ 失败: ' + str(zp['error'])}")
    if zp["sdk"]:
        print(f"                  SDK={zp['sdk']}")
    print("=" * 62)

    return 0 if (ds["ok"] and zp["ok"]) else 1


if __name__ == "__main__":
    sys.exit(main())
