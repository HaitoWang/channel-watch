from __future__ import annotations

import sqlite3
import time
from typing import Any

from apps.api.app.core.errors import ApiError
from apps.api.app.core.utils import optional_float

from ._http import http_json, unwrap_data
from .parsers import first_number, normalize_key_provider
from .rates import extract_model_rates, find_group, find_model_rate, infer_model_key
from .sub2api_auth import sub2api_access_token


def query_real_group(row: sqlite3.Row) -> dict[str, Any]:
    groups = query_real_group_catalog(row)
    target = find_group(groups, row["group_id"]) or (groups[0] if groups else None)
    if not target:
        raise ApiError(502, "未获取到可用分组")
    return target


def query_real_group_catalog(row: sqlite3.Row) -> list[dict[str, Any]]:
    if row["platform"] == "newApi":
        access_token = row["access_token"] or row["api_key"]
        user_id = row["user_id"]
        if not access_token or not user_id:
            raise ApiError(400, "newApi 缺少 accessToken/userId")
        headers = {"Authorization": f"Bearer {access_token}", "New-Api-User": str(user_id)}
        payload = http_json(
            "GET",
            f"{row['base_url'].rstrip('/')}/api/user/self/groups",
            headers,
        )
        groups = extract_newapi_groups(payload)
        if not groups:
            raise ApiError(502, "未获取到可用分组")
        return apply_model_multiplier_to_groups(
            row,
            groups,
            headers,
            ["/api/pricing", "/api/models", "/api/model-rates", "/api/user/self/pricing", "/api/user/self/models"],
        )
    token = sub2api_access_token(row)
    headers = {"Authorization": f"Bearer {token}"}
    groups_payload = http_json("GET", f"{row['base_url'].rstrip('/')}/api/v1/groups/available", headers)
    rates_payload = http_json("GET", f"{row['base_url'].rstrip('/')}/api/v1/groups/rates", headers)
    groups = extract_sub2api_groups(groups_payload, rates_payload)
    if not groups:
        raise ApiError(502, "未获取到可用分组")
    return apply_model_multiplier_to_groups(
        row,
        groups,
        headers,
        ["/api/v1/models/rates", "/api/v1/models/ratios", "/api/v1/models/available", "/api/v1/models", "/api/v1/pricing", "/api/pricing"],
    )


def extract_newapi_groups(payload: Any) -> list[dict[str, Any]]:
    data = unwrap_data(payload)
    if isinstance(data, dict):
        items = data.get("user_group") or data.get("userGroup") or data.get("groups") or data.get("items") or data.get("list")
        if not isinstance(items, list):
            items = [{"id": key, **value} for key, value in data.items() if isinstance(value, dict)]
    else:
        items = data
    result = []
    if not isinstance(items, list):
        return result
    for item in items:
        if not isinstance(item, dict):
            continue
        group_id = item.get("id") or item.get("name") or item.get("group") or item.get("groupName")
        if not group_id:
            continue
        rate = first_number(item, "effective_rate_multiplier", "rate", "ratio", "rate_multiplier", "rateMultiplier")
        name = item.get("plan_name") or item.get("planName") or item.get("desc") or item.get("description") or item.get("name") or str(group_id)
        result.append({"group_id": str(group_id), "group_name": str(name), "rate_multiplier": rate})
    return result


def extract_sub2api_groups(groups_payload: Any, rates_payload: Any) -> list[dict[str, Any]]:
    data = unwrap_data(groups_payload)
    if isinstance(data, dict):
        groups = data.get("items") or data.get("groups") or data.get("list") or []
    else:
        groups = data if isinstance(data, list) else []
    rates_data = unwrap_data(rates_payload)
    rates = rates_data if isinstance(rates_data, dict) else {}
    result = []
    for item in groups:
        if not isinstance(item, dict):
            continue
        group_id = item.get("id") or item.get("name")
        if group_id is None:
            continue
        user_rate = optional_float(rates.get(str(group_id))) if isinstance(rates, dict) else None
        default_rate = first_number(item, "default_rate_multiplier", "rate", "ratio", "rate_multiplier", "rateMultiplier")
        rate = first_number(item, "effective_rate_multiplier", "user_rate_multiplier", "userRateMultiplier")
        if rate is None:
            rate = user_rate if user_rate is not None else default_rate
        name = item.get("plan_name") or item.get("planName") or item.get("name") or f"分组 {group_id}"
        provider = normalize_key_provider(item.get("platform") or item.get("provider") or item.get("type") or name)
        result.append(
            {
                "group_id": str(group_id),
                "group_name": str(name),
                "rate_multiplier": rate,
                "platform": provider,
            }
        )
    return result


def apply_model_multiplier_to_groups(
    row: sqlite3.Row,
    groups: list[dict[str, Any]],
    headers: dict[str, str],
    endpoints: list[str],
) -> list[dict[str, Any]]:
    model_key = infer_model_key(row)
    if not model_key:
        return groups
    base_url = row["base_url"].rstrip("/")
    match: dict[str, Any] | None = None
    for endpoint in endpoints:
        try:
            payload = http_json("GET", f"{base_url}{endpoint}", headers)
        except ApiError:
            continue
        match = find_model_rate(extract_model_rates(payload), model_key)
        if match:
            break
    if not match:
        return groups
    model_rate = optional_float(match.get("rate_multiplier"))
    if model_rate is None:
        return groups
    enriched = []
    for group in groups:
        group_rate = optional_float(group.get("rate_multiplier") or group.get("rateMultiplier"))
        effective_rate = model_rate if group_rate is None else group_rate * model_rate
        enriched.append(
            {
                **group,
                "group_rate_multiplier": group_rate,
                "groupRateMultiplier": group_rate,
                "model_id": match["model_id"],
                "modelId": match["model_id"],
                "model_name": match.get("model_name") or match["model_id"],
                "modelName": match.get("model_name") or match["model_id"],
                "model_rate_multiplier": model_rate,
                "modelRateMultiplier": model_rate,
                "rate_multiplier": round(effective_rate, 6),
                "effective_rate_multiplier": round(effective_rate, 6),
                "effectiveRateMultiplier": round(effective_rate, 6),
            }
        )
    return enriched


def apply_model_multiplier(
    row: sqlite3.Row,
    target: dict[str, Any],
    headers: dict[str, str],
    endpoints: list[str],
) -> dict[str, Any]:
    model_key = infer_model_key(row)
    if not model_key:
        return target
    base_url = row["base_url"].rstrip("/")
    for endpoint in endpoints:
        try:
            payload = http_json("GET", f"{base_url}{endpoint}", headers)
        except ApiError:
            continue
        match = find_model_rate(extract_model_rates(payload), model_key)
        if not match:
            continue
        group_rate = optional_float(target.get("rate_multiplier"))
        model_rate = optional_float(match.get("rate_multiplier"))
        if model_rate is None:
            continue
        effective_rate = model_rate if group_rate is None else group_rate * model_rate
        return {
            **target,
            "group_rate_multiplier": group_rate,
            "groupRateMultiplier": group_rate,
            "model_id": match["model_id"],
            "modelId": match["model_id"],
            "model_name": match.get("model_name") or match["model_id"],
            "modelName": match.get("model_name") or match["model_id"],
            "model_rate_multiplier": model_rate,
            "modelRateMultiplier": model_rate,
            "rate_multiplier": round(effective_rate, 6),
            "effective_rate_multiplier": round(effective_rate, 6),
            "effectiveRateMultiplier": round(effective_rate, 6),
        }
    return target


def demo_group_result(row: sqlite3.Row) -> dict[str, Any]:
    current = optional_float(row["rate_multiplier"])
    if current is None:
        current = 1.0
    step = 0.1 if int(time.time() // 60 + row["id"]) % 3 == 0 else 0
    return {
        "group_id": row["group_id"] or "default",
        "group_name": row["group_name"] or "Default Pool",
        "rate_multiplier": round(current + step, 2),
    }
