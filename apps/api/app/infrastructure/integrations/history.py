from __future__ import annotations

import json
from typing import Any

from apps.api.app.core.utils import optional_float


def history_payload_summary(kind: str, payload_json: str | None, remaining: Any, rate_multiplier: Any) -> str:
    payload: Any = None
    if payload_json:
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError:
            payload = None
    if isinstance(payload, dict) and payload.get("error"):
        return str(payload["error"])
    if kind == "balance":
        unit = "USD"
        if isinstance(payload, dict):
            unit = str(payload.get("unit") or unit)
        value = optional_float(remaining)
        return f"余额 {value:g} {unit}" if value is not None else "余额探测完成"
    if kind == "group":
        rate = optional_float(rate_multiplier)
        group_name = None
        model_name = None
        model_rate = None
        group_rate = None
        if isinstance(payload, dict):
            group_name = payload.get("group_name") or payload.get("groupName") or payload.get("group_id")
            model_name = payload.get("model_name") or payload.get("modelName") or payload.get("model_id") or payload.get("modelId")
            model_rate = optional_float(payload.get("model_rate_multiplier") or payload.get("modelRateMultiplier"))
            group_rate = optional_float(payload.get("group_rate_multiplier") or payload.get("groupRateMultiplier"))
        if rate is not None and model_name and model_rate is not None:
            prefix = f"{group_name} · " if group_name else ""
            group_part = f"分组 {group_rate:g}x · " if group_rate is not None else ""
            return f"{prefix}{group_part}{model_name} 模型 {model_rate:g}x · 有效倍率 {rate:g}x"
        if rate is not None and group_name:
            return f"{group_name} · 倍率 {rate:g}"
        if rate is not None:
            return f"倍率 {rate:g}"
        return "倍率同步完成"
    if kind == "model":
        if isinstance(payload, dict):
            models = payload.get("models")
            failures = payload.get("failures") or []
            if failures:
                return "；".join(str(item) for item in failures[:2])
            if isinstance(models, list) and models:
                names = [str(item.get("model")) for item in models if isinstance(item, dict) and item.get("model")]
                return f"模型探测通过: {', '.join(names[:3])}" if names else "模型探测通过"
        return "模型探测完成"
    return "探测记录"
