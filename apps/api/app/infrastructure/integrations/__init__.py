from __future__ import annotations

import json
import re
import sqlite3
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

from apps.api.app.core.config import DEFAULT_TIMEOUT, DEFAULT_UPSTREAM_HEADERS
from apps.api.app.core.errors import ApiError
from apps.api.app.core.utils import bool_value, json_dumps, mask_secret, normalize_base_url, optional_float


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


def unwrap_data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


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


def sub2api_access_token(row: sqlite3.Row) -> str:
    if row["access_token"]:
        return str(row["access_token"])
    base_url = row["base_url"].rstrip("/")
    if row["refresh_token"]:
        auth = refresh_sub2api_session(base_url, row["refresh_token"])
        token = auth.get("access_token")
        if token:
            return token
    if not row["email"] or not row["password"]:
        raise ApiError(400, "sub2Api 查组缺少 accessToken/refreshToken 或 email/password")
    auth = login_sub2api_credentials(base_url, row["email"], row["password"])
    token = auth.get("access_token")
    if not token:
        raise ApiError(502, "sub2Api 登录成功但没有 access_token")
    return token


def login_sub2api_credentials(
    base_url: str,
    email: str,
    password: str,
    turnstile_token: str | None = None,
) -> dict[str, str | None]:
    url = normalize_base_url(base_url)
    body = {"email": email, "password": password}
    if turnstile_token:
        body["turnstile_token"] = turnstile_token
    payload = http_json(
        "POST",
        f"{url}/api/v1/auth/login",
        {"Origin": url, "Referer": f"{url}/login"},
        body,
    )
    auth = extract_auth_tokens(payload)
    if not auth.get("access_token"):
        raise ApiError(502, "sub2Api 登录成功但没有返回 access_token")
    return auth


def refresh_sub2api_session(base_url: str, refresh_token: str) -> dict[str, str | None]:
    url = normalize_base_url(base_url)
    payload = http_json(
        "POST",
        f"{url}/api/v1/auth/refresh",
        {"Origin": url, "Referer": f"{url}/login"},
        {"refresh_token": refresh_token},
    )
    auth = extract_auth_tokens(payload)
    if not auth.get("access_token"):
        raise ApiError(502, "sub2Api 刷新成功但没有返回 access_token")
    return auth


def extract_auth_tokens(payload: Any) -> dict[str, str | None]:
    return {
        "access_token": find_nested_text(payload, "access_token", "accessToken", "token"),
        "refresh_token": find_nested_text(payload, "refresh_token", "refreshToken"),
        "user_id": find_nested_text(payload, "user_id", "userId", "id"),
    }


def extract_access_token(payload: Any) -> str | None:
    data = unwrap_data(payload)
    if isinstance(data, dict):
        return data.get("access_token") or data.get("accessToken") or data.get("token")
    if isinstance(payload, dict):
        return payload.get("access_token") or payload.get("accessToken") or payload.get("token")
    return None


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


def query_sub2api_keys(row: sqlite3.Row) -> list[dict[str, Any]]:
    if row["platform"] != "sub2Api":
        return []
    token = sub2api_access_token(row)
    base_url = row["base_url"].rstrip("/")
    headers = {
        "Authorization": f"Bearer {token}",
        "Referer": f"{base_url}/keys",
    }
    page_size = 20
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in range(1, 101):
        params = urlencode(
            {
                "page": page,
                "page_size": page_size,
                "sort_by": "created_at",
                "sort_order": "desc",
                "timezone": "Asia/Shanghai",
            }
        )
        payload = http_json("GET", f"{base_url}/api/v1/keys?{params}", headers)
        items = extract_sub2api_keys(payload)
        new_count = 0
        for item in items:
            identity = key_identity(item)
            if not identity or identity in seen:
                continue
            seen.add(identity)
            result.append(item)
            new_count += 1
        total = payload_total_count(payload)
        if total is not None and len(result) >= total:
            break
        if len(items) < page_size or new_count == 0:
            break
    return result


def extract_sub2api_keys(payload: Any) -> list[dict[str, Any]]:
    items = extract_key_items(payload)
    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        external_key_id = first_text(
            item,
            "id",
            "key_id",
            "keyId",
            "api_key_id",
            "apiKeyId",
            "apiKeyID",
        )
        direct_key = first_text(item, "api_key", "apiKey", "key_value", "keyValue", "secret_key", "secretKey")
        generic_key = first_text(item, "key", "token", "secret")
        masked_key = first_text(
            item,
            "api_key_masked",
            "apiKeyMasked",
            "masked_api_key",
            "maskedApiKey",
            "masked_key",
            "maskedKey",
            "key_masked",
            "keyMasked",
            "display_key",
            "displayKey",
        )
        api_key = direct_key
        if api_key and looks_masked_secret(api_key):
            masked_key = masked_key or api_key
            api_key = None
        if not api_key and generic_key:
            if looks_masked_secret(generic_key):
                masked_key = masked_key or generic_key
            elif looks_like_api_secret(generic_key):
                api_key = generic_key
        if api_key and not masked_key:
            masked_key = mask_secret(api_key)

        group = item.get("group")
        group_id = first_text(item, "group_id", "groupId", "group")
        group_name = first_text(item, "group_name", "groupName")
        if isinstance(group, dict):
            group_id = group_id or first_text(group, "id", "group_id", "groupId", "name")
            group_name = group_name or first_text(group, "name", "group_name", "groupName", "title")
        elif group is not None:
            group_id = group_id or str(group)

        models = item.get("models") or item.get("model_ids") or item.get("modelIds")
        if isinstance(models, list):
            model_scope = ", ".join(str(model) for model in models if str(model).strip())
        else:
            model_scope = first_text(item, "model_scope", "modelScope", "model", "model_name", "modelName")

        provider_value = first_text(
            item,
            "key_provider",
            "keyProvider",
            "provider_type",
            "providerType",
            "key_type",
            "keyType",
            "api_type",
            "apiType",
            "service_type",
            "serviceType",
            "provider",
            "type",
        )
        provider = item.get("provider")
        if isinstance(provider, dict):
            provider_value = provider_value or first_text(provider, "type", "name", "id", "provider")
        if isinstance(group, dict):
            provider_value = provider_value or first_text(
                group,
                "platform",
                "provider",
                "provider_type",
                "providerType",
                "type",
                "name",
                "group_name",
                "groupName",
            )
        key_provider = normalize_key_provider(provider_value) or normalize_key_provider(model_scope)

        enabled_value = (
            item.get("is_enabled")
            if "is_enabled" in item
            else item.get("isEnabled")
            if "isEnabled" in item
            else item.get("enabled")
        )
        status_text = str(item.get("status") or "").strip().lower()
        if enabled_value is None and status_text:
            enabled_value = status_text not in {"disabled", "disable", "inactive", "revoked", "deleted", "false", "0"}

        result.append(
            {
                "external_key_id": external_key_id,
                "externalKeyId": external_key_id,
                "key_name": first_text(item, "name", "label", "title", "remark", "description", "note") or external_key_id,
                "keyName": first_text(item, "name", "label", "title", "remark", "description", "note") or external_key_id,
                "api_key": api_key,
                "apiKey": api_key,
                "api_key_masked": masked_key,
                "apiKeyMasked": masked_key,
                "key_provider": key_provider,
                "keyProvider": key_provider,
                "group_id": group_id,
                "groupId": group_id,
                "group_name": group_name,
                "groupName": group_name,
                "model_scope": model_scope,
                "modelScope": model_scope,
                "is_enabled": True if enabled_value is None else bool_value(enabled_value),
                "isEnabled": True if enabled_value is None else bool_value(enabled_value),
                "raw": item,
            }
        )
    return result


def extract_key_items(payload: Any) -> list[dict[str, Any]]:
    container_keys = (
        "items",
        "keys",
        "api_keys",
        "apiKeys",
        "records",
        "results",
        "rows",
        "list",
        "data",
    )

    def walk(value: Any, depth: int = 0) -> list[dict[str, Any]]:
        value = unwrap_data(value)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if not isinstance(value, dict) or depth > 5:
            return []
        for key in container_keys:
            nested = value.get(key)
            if nested is None:
                continue
            items = walk(nested, depth + 1)
            if items:
                return items
        if any(key in value for key in ("id", "api_key", "apiKey", "key_id", "api_key_id", "key")):
            return [value]
        for nested in value.values():
            items = walk(nested, depth + 1)
            if items:
                return items
        return []

    return walk(payload)


def payload_total_count(payload: Any) -> int | None:
    candidates: list[Any] = [payload, unwrap_data(payload)]
    if isinstance(payload, dict):
        candidates.extend([payload.get("meta"), payload.get("pagination"), payload.get("page")])
        data = unwrap_data(payload)
        if isinstance(data, dict):
            candidates.extend([data.get("meta"), data.get("pagination"), data.get("page")])
    for candidate in candidates:
        if isinstance(candidate, dict):
            total = first_number(candidate, "total", "total_count", "totalCount", "count")
            if total is not None:
                return int(total)
    return None


def key_identity(item: dict[str, Any]) -> str | None:
    value = (
        item.get("external_key_id")
        or item.get("externalKeyId")
        or item.get("api_key")
        or item.get("apiKey")
        or item.get("api_key_masked")
        or item.get("apiKeyMasked")
        or item.get("key_name")
        or item.get("keyName")
    )
    return str(value).strip() if value else None


def public_key_items(keys: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "external_key_id": item.get("external_key_id") or item.get("externalKeyId"),
            "externalKeyId": item.get("external_key_id") or item.get("externalKeyId"),
            "key_name": item.get("key_name") or item.get("keyName"),
            "keyName": item.get("key_name") or item.get("keyName"),
            "key_masked": item.get("api_key_masked") or item.get("apiKeyMasked") or mask_secret(item.get("api_key") or item.get("apiKey")),
            "keyMasked": item.get("api_key_masked") or item.get("apiKeyMasked") or mask_secret(item.get("api_key") or item.get("apiKey")),
            "key_provider": item.get("key_provider") or item.get("keyProvider"),
            "keyProvider": item.get("key_provider") or item.get("keyProvider"),
            "group_id": item.get("group_id") or item.get("groupId"),
            "groupId": item.get("group_id") or item.get("groupId"),
        }
        for item in keys
    ]


def imported_key_matches_channel(row: sqlite3.Row, item: dict[str, Any]) -> bool:
    current = str(row["api_key"] or "").strip()
    if not current:
        return False
    api_key = str(item.get("api_key") or item.get("apiKey") or "").strip()
    if api_key and api_key == current:
        return True
    masked = str(item.get("api_key_masked") or item.get("apiKeyMasked") or item.get("key_masked") or item.get("keyMasked") or "").strip()
    return bool(masked and len(current) >= 8 and current[:2] in masked and current[-4:] in masked)


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


def looks_masked_secret(value: Any) -> bool:
    text = str(value or "")
    return any(marker in text for marker in ("•", "*", "…", "..."))


def looks_like_api_secret(value: Any) -> bool:
    text = str(value or "").strip()
    if looks_masked_secret(text) or len(text) < 16 or any(char.isspace() for char in text):
        return False
    return text.startswith(("sk-", "sk_", "sub", "sess-", "key-")) or bool(re.search(r"[-_][A-Za-z0-9]{8,}", text))


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


def normalize_model_name(value: Any) -> str:
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", str(value or "").strip().lower())


def find_group(groups: list[dict[str, Any]], group_id: Any) -> dict[str, Any] | None:
    if not group_id:
        return None
    target = str(group_id)
    return next((item for item in groups if str(item.get("group_id")) == target), None)


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
