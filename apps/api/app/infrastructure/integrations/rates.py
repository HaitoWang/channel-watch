from __future__ import annotations

import re
import sqlite3
from typing import Any

from apps.api.app.core.utils import optional_float

from ._http import unwrap_data
from .parsers import first_number, first_text, normalize_model_name


def infer_model_key(row: sqlite3.Row) -> str | None:
    texts = [str(row["model_scope"] or ""), str(row["name"] or "")]
    for text in texts:
        normalized = normalize_model_name(text)
        if not normalized or normalized in {"allmodels", "all", "全部模型", "全部"}:
            continue
        if "codex" in normalized:
            return "codex"
    for text in texts:
        parts = [part for part in re.split(r"[\s,，/|:：_\-]+", text.strip().lower()) if part]
        parts = [part for part in parts if normalize_model_name(part) not in {"allmodels", "all", "ai", "api", "聪明ai"}]
        if "codex" in parts:
            return "codex"
        if len(parts) == 1:
            return parts[0]
        if parts:
            return parts[-1]
    return None


def extract_model_rates(payload: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    rate_keys = (
        "model_rate_multiplier",
        "modelRateMultiplier",
        "model_ratio",
        "modelRatio",
        "rate_multiplier",
        "rateMultiplier",
        "effective_rate_multiplier",
        "effectiveRateMultiplier",
        "ratio",
        "rate",
        "multiplier",
        "倍率",
    )
    model_keys = ("model", "model_id", "modelId", "model_name", "modelName", "id", "name", "key")
    container_keys = (
        "models",
        "model_rates",
        "modelRates",
        "model_ratios",
        "modelRatios",
        "rates",
        "ratios",
        "items",
        "list",
        "pricing",
        "prices",
        "data",
    )

    def add(model_id: Any, model_name: Any, rate: Any) -> None:
        model_text = str(model_id or "").strip()
        rate_value = optional_float(rate)
        if not model_text or rate_value is None:
            return
        key = normalize_model_name(model_text)
        if not key or key in seen:
            return
        seen.add(key)
        result.append(
            {
                "model_id": model_text,
                "modelId": model_text,
                "model_name": str(model_name or model_text),
                "modelName": str(model_name or model_text),
                "rate_multiplier": rate_value,
                "rateMultiplier": rate_value,
            }
        )

    def walk(value: Any) -> None:
        value = unwrap_data(value)
        if isinstance(value, list):
            for item in value:
                walk(item)
            return
        if not isinstance(value, dict):
            return
        model_id = first_text(value, *model_keys)
        rate = first_number(value, *rate_keys)
        if model_id and rate is not None:
            add(model_id, value.get("display_name") or value.get("displayName") or value.get("label") or model_id, rate)
        for key, item in value.items():
            if key in container_keys:
                walk(item)
                continue
            if isinstance(item, (int, float, str)):
                add(key, key, item)
                continue
            if isinstance(item, dict):
                nested_rate = first_number(item, *rate_keys)
                nested_name = first_text(item, *model_keys) or key
                if nested_rate is not None:
                    add(nested_name, item.get("display_name") or item.get("displayName") or item.get("label") or nested_name, nested_rate)
                else:
                    walk(item)
            elif isinstance(item, list):
                walk(item)

    walk(payload)
    return result


def find_model_rate(models: list[dict[str, Any]], model_key: str) -> dict[str, Any] | None:
    target = normalize_model_name(model_key)
    if not target:
        return None
    exact = [item for item in models if normalize_model_name(item.get("model_id")) == target]
    if exact:
        return exact[0]
    contains = [
        item
        for item in models
        if target in normalize_model_name(item.get("model_id")) or normalize_model_name(item.get("model_id")) in target
    ]
    if not contains:
        return None
    return sorted(contains, key=lambda item: len(str(item.get("model_id") or "")))[0]


def find_group(groups: list[dict[str, Any]], group_id: Any) -> dict[str, Any] | None:
    if not group_id:
        return None
    target = str(group_id)
    return next((item for item in groups if str(item.get("group_id")) == target), None)
