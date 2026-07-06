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
    # OpenAI 类：优先 /v1/chat/completions + stream:false（多数上游返回干净 JSON），
    # 失败再回落 /v1/responses（部分上游强制 SSE 流，已支持解析）。
    try:
        payload = probe_chat_completions(base_url, api_key, model_name)
        return {
            "ok": True,
            "model": model_name,
            "protocol": "chat.completions",
            "summary": extract_probe_text(payload) or "chat.completions 响应正常",
            "raw": payload,
        }
    except ApiError as exc:
        # 端点不存在/不支持才回落 responses；鉴权/额度类错误直接抛出
        if exc.status not in {400, 404, 405, 501}:
            raise
    payload = probe_responses_api(base_url, api_key, model_name)
    return {
        "ok": True,
        "model": model_name,
        "protocol": "responses",
        "summary": extract_probe_text(payload) or "responses 响应正常",
        "raw": payload,
    }


def probe_chat_completions(base_url: str, api_key: str, model_name: str) -> Any:
    """走 /v1/chat/completions + stream:false，多数上游返回干净 JSON。"""
    return http_json(
        "POST",
        api_url(base_url, "/v1/chat/completions"),
        {"Authorization": f"Bearer {api_key}"},
        {
            "model": model_name,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 16,
            "stream": False,
        },
        allow_sse=True,
    )


def probe_responses_api(base_url: str, api_key: str, model_name: str) -> Any:
    """调用 Responses API 探测。不同上游/代理对可选参数支持不一，
    遇到「Unsupported parameter」类 400 时逐步剥离可选参数重试，
    最终回落到只带 model + input 的最小请求体。"""
    url = api_url(base_url, "/v1/responses")
    headers = {"Authorization": f"Bearer {api_key}"}
    base_body = {
        "model": model_name,
        "input": [{"role": "user", "content": "ping"}],
    }
    # 从最完整到最精简：每次遇到不支持的参数就退到下一档
    variants = [
        {**base_body, "max_output_tokens": 16, "store": False},
        {**base_body, "max_output_tokens": 16},
        {**base_body, "store": False},
        base_body,
    ]
    last_exc: ApiError | None = None
    for body in variants:
        try:
            return http_json("POST", url, headers, body, allow_sse=True)
        except ApiError as exc:
            if exc.status == 400 and _is_unsupported_param_error(exc.message):
                last_exc = exc
                continue
            raise
    if last_exc is not None:
        raise last_exc
    raise ApiError(502, "responses 探测失败")


def _is_unsupported_param_error(message: Any) -> bool:
    text = str(message or "").lower()
    return "unsupported parameter" in text or "unknown parameter" in text or "unexpected parameter" in text


def extract_probe_text(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    output_text = payload.get("output_text")
    if output_text:
        return str(output_text)[:120]
    # chat.completions 格式：choices[].message.content
    choices = payload.get("choices")
    if isinstance(choices, list):
        for item in choices:
            if not isinstance(item, dict):
                continue
            message = item.get("message")
            if isinstance(message, dict) and message.get("content"):
                return str(message["content"])[:120]
            if item.get("text"):
                return str(item["text"])[:120]
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
