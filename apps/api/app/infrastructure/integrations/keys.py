from __future__ import annotations

import re
import sqlite3
from typing import Any
from urllib.parse import urlencode

from apps.api.app.core.utils import bool_value, mask_secret

from ._http import http_json, unwrap_data
from .parsers import first_number, first_text, normalize_key_provider
from .sub2api_auth import sub2api_access_token


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


def looks_masked_secret(value: Any) -> bool:
    text = str(value or "")
    return any(marker in text for marker in ("•", "*", "…", "..."))


def looks_like_api_secret(value: Any) -> bool:
    text = str(value or "").strip()
    if looks_masked_secret(text) or len(text) < 16 or any(char.isspace() for char in text):
        return False
    return text.startswith(("sk-", "sk_", "sub", "sess-", "key-")) or bool(re.search(r"[-_][A-Za-z0-9]{8,}", text))

