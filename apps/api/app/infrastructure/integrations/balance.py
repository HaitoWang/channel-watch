from __future__ import annotations

import sqlite3
import time
from typing import Any

from apps.api.app.core.errors import ApiError
from apps.api.app.core.utils import optional_float

from ._http import http_json
from .parsers import find_nested_number, find_nested_text
from .sub2api_auth import sub2api_access_token


def query_real_balance(row: sqlite3.Row) -> dict[str, Any]:
    base_url = row["base_url"].rstrip("/")
    if row["platform"] == "sub2Api":
        return query_sub2api_account_balance(row)
    access_token = row["access_token"] or row["api_key"]
    user_id = row["user_id"]
    if not access_token:
        raise ApiError(400, "newApi 缺少 accessToken")
    if not user_id:
        raise ApiError(400, "newApi 缺少 userId")
    payload = http_json(
        "GET",
        f"{base_url}/api/user/self",
        {"Authorization": f"Bearer {access_token}", "New-Api-User": str(user_id)},
    )
    if isinstance(payload, dict) and payload.get("success") and isinstance(payload.get("data"), dict):
        data = payload["data"]
        quota = optional_float(data.get("quota")) or 0
        used_quota = optional_float(data.get("used_quota")) or 0
        return {
            "is_valid": True,
            "remaining": round(quota / 500000, 6),
            "used": round(used_quota / 500000, 6),
            "total": round((quota + used_quota) / 500000, 6),
            "unit": "USD",
            "plan_name": data.get("group") or "默认套餐",
            "raw": payload,
        }
    raise ApiError(502, str(payload.get("message") if isinstance(payload, dict) else "newApi 查询失败"))


def query_sub2api_account_balance(row: sqlite3.Row) -> dict[str, Any]:
    base_url = row["base_url"].rstrip("/")
    token = sub2api_access_token(row)
    payload = http_json(
        "GET",
        f"{base_url}/api/v1/auth/me?timezone=Asia%2FShanghai",
        {
            "Authorization": f"Bearer {token}",
            "Referer": f"{base_url}/keys",
        },
    )
    result = extract_balance_result(payload)
    if not result:
        raise ApiError(502, "sub2Api auth/me 接口未返回可识别余额字段")
    result["source"] = "/api/v1/auth/me"
    result["raw"] = payload
    return result


def extract_balance_result(payload: Any) -> dict[str, Any] | None:
    remaining = find_nested_number(
        payload,
        "remaining",
        "remain",
        "remain_quota",
        "remainQuota",
        "available",
        "available_quota",
        "availableQuota",
        "balance",
        "credit",
        "credits",
        "quota",
    )
    used = find_nested_number(payload, "used", "used_quota", "usedQuota", "usage", "consumed", "spent")
    total = find_nested_number(payload, "total", "total_quota", "totalQuota", "quota_total", "quotaTotal", "limit")
    if remaining is None and total is not None and used is not None:
        remaining = max(0, total - used)
    if remaining is None:
        return None
    unit = find_nested_text(payload, "unit", "currency") or "USD"
    return {
        "is_valid": True,
        "remaining": remaining,
        "used": used,
        "total": total,
        "unit": unit,
        "plan_name": find_nested_text(payload, "planName", "plan_name", "plan", "group", "group_name", "groupName"),
    }


def demo_balance_result(row: sqlite3.Row) -> dict[str, Any]:
    seed = int(time.time() // 30) + int(row["id"]) * 11
    current = optional_float(row["balance"])
    threshold = optional_float(row["threshold"]) or 10
    if current is None:
        current = threshold * 2.8
    drift = ((seed % 9) - 4) * 0.37
    remaining = max(0, current + drift)
    if row["status"] == "offline":
        remaining = threshold * 0.62
    total = optional_float(row["quota_total"]) or max(threshold * 5, remaining * 1.45)
    used = max(0, total - remaining)
    return {
        "is_valid": True,
        "remaining": round(remaining, 2),
        "unit": row["unit"] or "USD",
        "total": round(total, 2),
        "used": round(used, 2),
        "plan_name": row["group_name"] or "Demo Plan",
        "raw": {"mode": "demo"},
    }
