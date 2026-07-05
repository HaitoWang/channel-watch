from __future__ import annotations

import sqlite3
from typing import Any

from apps.api.app.core.errors import ApiError

from ._http import api_url, http_json
from .parsers import normalize_model_name, normalize_probe_model


def query_model_probe(row: sqlite3.Row, model: str) -> dict[str, Any]:
    api_key = row["api_key"]
    if not api_key:
        raise ApiError(400, "模型监控缺少 apiKey")
    model_name = normalize_probe_model(str(model or "").strip())
    if not model_name:
        raise ApiError(400, "模型名称不能为空")
    base_url = row["base_url"].rstrip("/")
    if "claude" in normalize_model_name(model_name):
        payload = http_json(
            "POST",
            api_url(base_url, "/v1/messages"),
            {
                "Authorization": f"Bearer {api_key}",
                "x-api-key": str(api_key),
                "anthropic-version": "2023-06-01",
            },
            {
                "model": model_name,
                "max_tokens": 16,
                "messages": [{"role": "user", "content": "ping"}],
            },
        )
        return {
            "ok": True,
            "model": model_name,
            "protocol": "messages",
            "summary": extract_probe_text(payload) or "messages 响应正常",
            "raw": payload,
        }
    payload = http_json(
        "POST",
        api_url(base_url, "/v1/responses"),
        {"Authorization": f"Bearer {api_key}"},
        {
            "model": model_name,
            "input": "ping",
            "max_output_tokens": 16,
            "store": False,
        },
    )
    return {
        "ok": True,
        "model": model_name,
        "protocol": "responses",
        "summary": extract_probe_text(payload) or "responses 响应正常",
        "raw": payload,
    }


def extract_probe_text(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    output_text = payload.get("output_text")
    if output_text:
        return str(output_text)[:120]
    text = payload.get("text")
    if text:
        return str(text)[:120]
    content = payload.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("text"):
                return str(item["text"])[:120]
    output = payload.get("output")
    if isinstance(output, list):
        for item in output:
            if isinstance(item, dict):
                text = extract_probe_text(item)
                if text:
                    return text
    return None
