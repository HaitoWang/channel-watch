from __future__ import annotations

import http.client
import json
import socket
import ssl
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from apps.api.app.core.config import DEFAULT_TIMEOUT, DEFAULT_UPSTREAM_HEADERS
from apps.api.app.core.errors import ApiError
from apps.api.app.core.utils import json_dumps

# 瞬时连接层错误（TLS 握手中断、连接重置、超时等）——自动重试可缓解。
# 注意：urllib.error.HTTPError 是 URLError 的子类，但它带有响应体（业务错误），
# 在下方单独先行捕获、不参与重试。
_RETRYABLE_EXC = (
    urllib.error.URLError,
    ssl.SSLError,
    ConnectionError,
    TimeoutError,
    socket.timeout,
    http.client.HTTPException,
)
_MAX_RETRIES = 2
_RETRY_BACKOFF = 0.5


def http_json(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    *,
    retries: int = _MAX_RETRIES,
    allow_sse: bool = False,
) -> Any:
    body = None
    request_headers = {**DEFAULT_UPSTREAM_HEADERS, **(headers or {})}
    if payload is not None:
        body = json_dumps(payload)
        request_headers["Content-Type"] = "application/json"

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
                raw = response.read()
                content_type = response.headers.get("Content-Type", "")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise ApiError(exc.code, f"上游 HTTP {exc.code}: {detail or exc.reason}") from exc
        except _RETRYABLE_EXC as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(_RETRY_BACKOFF * (2 ** attempt))
                continue
            reason = getattr(exc, "reason", None) or exc
            raise ApiError(502, f"上游请求失败: {reason}") from exc
        text = raw.decode("utf-8", errors="replace")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            # 有些上游（尤其 /v1/responses）强制返回 SSE 流，需按事件流解析
            if allow_sse and ("text/event-stream" in content_type.lower() or text.lstrip().startswith("event:") or "\ndata:" in text or text.startswith("data:")):
                parsed = parse_sse_events(text)
                if parsed is not None:
                    return parsed
            raise ApiError(502, "上游返回不是 JSON") from exc

    # 理论不可达（循环内要么 return 要么 raise）
    reason = getattr(last_error, "reason", None) or last_error
    raise ApiError(502, f"上游请求失败: {reason}")


def parse_sse_events(text: str) -> Any:
    """解析 SSE(text/event-stream)响应，返回聚合后的最终对象。

    优先取带完整 response/结果的事件（如 response.completed），
    否则回落到最后一个可解析的 data JSON。用于模型探测这类只需
    确认「上游有正常响应」的场景。"""
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        data = line[len("data:"):].strip()
        if not data or data == "[DONE]":
            continue
        try:
            events.append(json.loads(data))
        except json.JSONDecodeError:
            continue
    if not events:
        return None
    # 优先返回"完成"类事件里的 response 对象
    for event in reversed(events):
        etype = str(event.get("type") or "")
        if etype.endswith("completed") and isinstance(event.get("response"), dict):
            return event["response"]
    for event in reversed(events):
        if isinstance(event.get("response"), dict):
            return event["response"]
    return events[-1]


def api_url(base_url: str, path: str) -> str:
    base = str(base_url or "").rstrip("/")
    clean_path = "/" + str(path or "").lstrip("/")
    parts = urlsplit(base)
    base_path = parts.path.rstrip("/")
    if base_path.endswith("/v1") and clean_path.startswith("/v1/"):
        clean_path = clean_path[3:]
    return urlunsplit((parts.scheme, parts.netloc, f"{base_path}{clean_path}", "", ""))


def unwrap_data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload
