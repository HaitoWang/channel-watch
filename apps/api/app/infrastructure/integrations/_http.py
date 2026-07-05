from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from apps.api.app.core.config import DEFAULT_TIMEOUT, DEFAULT_UPSTREAM_HEADERS
from apps.api.app.core.errors import ApiError
from apps.api.app.core.utils import json_dumps


def http_json(method: str, url: str, headers: dict[str, str] | None = None, payload: dict[str, Any] | None = None) -> Any:
    body = None
    request_headers = {**DEFAULT_UPSTREAM_HEADERS, **(headers or {})}
    if payload is not None:
        body = json_dumps(payload)
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise ApiError(exc.code, f"上游 HTTP {exc.code}: {detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ApiError(502, f"上游请求失败: {exc.reason}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ApiError(502, "上游返回不是 JSON") from exc


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
