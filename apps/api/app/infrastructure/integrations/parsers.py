from __future__ import annotations

import json
import re
from typing import Any

from apps.api.app.core.utils import optional_float

from ._http import unwrap_data


def normalize_model_name(value: Any) -> str:
    return re.sub(r"[^0-9a-zA-Z一-鿿]+", "", str(value or "").strip().lower())


def normalize_probe_model(model: str) -> str:
    model_name = str(model or "").strip()
    if re.fullmatch(r"(?i)gpt\s*-?\s*5\.5", model_name):
        return "gpt-5.5"
    return model_name


def normalize_key_provider(value: Any) -> str | None:
    normalized = normalize_model_name(value)
    if not normalized:
        return None
    if "anthropic" in normalized or "claude" in normalized:
        return "anthropic"
    if "openai" in normalized or "gpt" in normalized or normalized in {"chatgpt"}:
        return "openai"
    return None


def first_number(item: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in item:
            value = optional_float(item.get(key))
            if value is not None:
                return value
    return None


def first_text(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def find_nested_text(payload: Any, *keys: str) -> str | None:
    seen: set[int] = set()

    def walk(value: Any) -> str | None:
        value = unwrap_data(value)
        if isinstance(value, dict):
            object_id = id(value)
            if object_id in seen:
                return None
            seen.add(object_id)
            for key in keys:
                text = value.get(key)
                if text is not None and str(text).strip():
                    return str(text).strip()
            for nested in value.values():
                found = walk(nested)
                if found:
                    return found
        elif isinstance(value, list):
            for nested in value:
                found = walk(nested)
                if found:
                    return found
        return None

    return walk(payload)


def find_nested_number(payload: Any, *keys: str) -> float | None:
    seen: set[int] = set()

    def walk(value: Any) -> float | None:
        value = unwrap_data(value)
        if isinstance(value, dict):
            object_id = id(value)
            if object_id in seen:
                return None
            seen.add(object_id)
            for key in keys:
                if key in value:
                    number = optional_float(value.get(key))
                    if number is not None:
                        return number
            for nested in value.values():
                found = walk(nested)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for nested in value:
                found = walk(nested)
                if found is not None:
                    return found
        return None

    return walk(payload)


def group_payload(payload_json: str | None) -> dict[str, Any]:
    if not payload_json:
        return {}
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    allowed = {
        "group_rate_multiplier",
        "groupRateMultiplier",
        "model_id",
        "modelId",
        "model_name",
        "modelName",
        "model_rate_multiplier",
        "modelRateMultiplier",
        "effective_rate_multiplier",
        "effectiveRateMultiplier",
    }
    return {key: value for key, value in payload.items() if key in allowed}
