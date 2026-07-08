"""我方 sub2api 号池的写动作封装。

监控系统（channel-watc）根据上游指标，调用我方 sub2api 的 admin 接口
开关号池账号（account）的调度状态：

    POST {base_url}/api/v1/admin/accounts/{account_id}/schedulable
    Header: x-api-key: <admin-api-key>
    Body:   {"schedulable": true|false}

复用项目内 urllib 封装 http_json，不引入第三方依赖。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlencode

from apps.api.app.core.config import DEFAULT_UPSTREAM_HEADERS
from apps.api.app.core.errors import ApiError
from apps.api.app.core.utils import normalize_base_url

from ._http import http_json


def set_account_schedulable(
    base_url: str,
    admin_api_key: str,
    account_id: str | int,
    enabled: bool,
) -> Any:
    """开关我方号池账号调度。成功返回上游响应体，失败抛 ApiError。"""
    base = normalize_base_url(base_url)
    if not base:
        raise ApiError(400, "号池 Base URL 未配置")
    if not str(admin_api_key or "").strip():
        raise ApiError(400, "号池 Admin API Key 未配置")
    account = str(account_id).strip()
    if not account:
        raise ApiError(400, "缺少号池账号 ID")
    headers = {
        "x-api-key": str(admin_api_key).strip(),
        "Referer": f"{base}/accounts",
    }
    return http_json(
        "POST",
        f"{base}/api/v1/admin/accounts/{account}/schedulable",
        headers,
        {"schedulable": bool(enabled)},
    )


def set_account_priority(
    base_url: str,
    admin_api_key: str,
    account_id: str | int,
    priority: int,
) -> Any:
    """设置号池账号调度优先级（越小越优先）。PUT /api/v1/admin/accounts/{id}。"""
    base = normalize_base_url(base_url)
    if not base:
        raise ApiError(400, "号池 Base URL 未配置")
    if not str(admin_api_key or "").strip():
        raise ApiError(400, "号池 Admin API Key 未配置")
    account = str(account_id).strip()
    if not account:
        raise ApiError(400, "缺少号池账号 ID")
    headers = {
        "x-api-key": str(admin_api_key).strip(),
        "Referer": f"{base}/accounts",
    }
    return http_json(
        "PUT",
        f"{base}/api/v1/admin/accounts/{account}",
        headers,
        {"priority": int(priority)},
    )


def test_account(
    base_url: str,
    admin_api_key: str,
    account_id: str | int,
    model: str | None = None,
    *,
    timeout: int = 60,
) -> dict[str, Any]:
    """让我方 sub2api 测试指定账号的连通性（借道 admin key，避开直连上游的 CF/盾）。

    调 POST /api/v1/admin/accounts/{id}/test，响应是 SSE 流：
      data: {"type":"test_start",...}
      data: {"type":"test_complete","success":true}   ← 成功
      data: {"type":"error","error":"..."}            ← 失败
    返回 {"ok": bool, "message": str}。
    """
    base = normalize_base_url(base_url)
    if not base:
        raise ApiError(400, "号池 Base URL 未配置")
    if not str(admin_api_key or "").strip():
        raise ApiError(400, "号池 Admin API Key 未配置")
    account = str(account_id).strip()
    if not account:
        raise ApiError(400, "缺少号池账号 ID")

    body: dict[str, Any] = {}
    if model:
        body["model_id"] = model
    data = json.dumps(body).encode("utf-8")
    headers = {
        **DEFAULT_UPSTREAM_HEADERS,
        "x-api-key": str(admin_api_key).strip(),
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "Referer": f"{base}/accounts",
    }
    url = f"{base}/api/v1/admin/accounts/{account}/test"
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:200]
        raise ApiError(exc.code, f"号池测账号 HTTP {exc.code}: {detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ApiError(502, f"号池测账号请求失败: {exc.reason}") from exc

    return _parse_test_sse(raw)


def recent_first_token_ms(
    base_url: str,
    admin_api_key: str,
    account_id: str | int,
    sample: int = 10,
    *,
    timeout: int = 20,
) -> list[int]:
    """查该账号最近 N 次「流式」请求的首 token 耗时（毫秒）。

    调 GET /api/v1/admin/usage?request_type=stream&stream=true&account_id=...，
    提取每条的 first_token_ms（过滤空值），按时间倒序返回。用于判断"能用但卡"。
    """
    base = normalize_base_url(base_url)
    if not base or not str(admin_api_key or "").strip():
        return []
    account = str(account_id).strip()
    if not account:
        return []
    params = urlencode({
        "page": 1,
        "page_size": max(1, int(sample)),
        "exact_total": "false",
        "request_type": "stream",
        "stream": "true",
        "account_id": account,
        "sort_by": "created_at",
        "sort_order": "desc",
        "timezone": "Asia/Shanghai",
    })
    headers = {
        "x-api-key": str(admin_api_key).strip(),
        "Accept": "application/json",
        "Referer": f"{base}/usage",
    }
    payload = http_json("GET", f"{base}/api/v1/admin/usage?{params}", headers, retries=1)
    data = payload.get("data") if isinstance(payload, dict) else None
    items = (data or {}).get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    result: list[int] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        ft = item.get("first_token_ms")
        if isinstance(ft, (int, float)) and ft >= 0:
            result.append(int(ft))
    return result


def _is_transient_error(message: str) -> bool:
    """瞬时错误：账号本身正常，只是此刻忙/上游临时抽风，不应判为故障。

    含限流(429)、过载、以及上游临时不可用(500/502/503/504、gateway/timeout 等)。
    """
    m = message.lower()
    keywords = (
        "429", "rate_limit", "rate limit", "too many", "pending requests",
        "please retry", "overloaded", "try again",
        "500", "502", "503", "504",
        "temporarily unavailable", "service unavailable", "bad gateway",
        "gateway timeout", "timeout", "timed out", "upstream", "内部错误",
    )
    return any(k in m for k in keywords)


def _parse_test_sse(text: str) -> dict[str, Any]:
    """解析测账号 SSE 流，判定成功/失败/瞬时繁忙。"""
    success = False
    error_msg = ""
    saw_complete = False
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            continue
        etype = str(event.get("type") or "")
        if etype == "test_complete":
            saw_complete = True
            if event.get("success"):
                success = True
        elif etype == "error":
            error_msg = str(event.get("error") or "测试失败")
        elif event.get("error") and not error_msg:
            error_msg = str(event.get("error"))
    if success:
        return {"ok": True, "message": "连通正常"}
    if not saw_complete and not error_msg:
        error_msg = "未收到测试完成事件"
    # 限流/繁忙：视为瞬时，不判故障（保持上次状态）
    if error_msg and _is_transient_error(error_msg):
        return {"ok": True, "transient": True, "message": f"账号繁忙（{error_msg[:60]}），跳过本轮"}
    return {"ok": False, "message": error_msg or "测试失败"}
