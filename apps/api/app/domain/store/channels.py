from __future__ import annotations

import json
import sqlite3
from typing import Any

from apps.api.app.core.errors import ApiError
from apps.api.app.infrastructure.integrations import find_group, group_payload, imported_key_matches_channel, login_sub2api_credentials, normalize_key_provider
from apps.api.app.core.utils import bool_value, mask_secret, normalize_base_url, optional_float, utc_now


DEFAULT_MONITOR_MODELS = ["gpt-5.5", "claude-sonnet-4-5"]
PROVIDER_MONITOR_MODELS = {
    "openai": ["gpt-5.5"],
    "anthropic": ["claude-sonnet-4-5"],
}


class ChannelRepositoryMixin:
    active_channel_filter = """
        NOT (
            c.platform = 'sub2Api'
            AND c.api_key IS NULL
            AND c.external_key_id IS NULL
            AND (c.access_token IS NOT NULL OR c.refresh_token IS NOT NULL OR c.email IS NOT NULL)
            AND EXISTS (
                SELECT 1
                FROM channels child
                WHERE child.source_channel_id = c.id
                  AND (child.api_key IS NOT NULL OR child.external_key_id IS NOT NULL)
            )
        )
    """

    def list_channels(self, status: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT c.*
                FROM channels c
                WHERE {self.active_channel_filter}
                ORDER BY CASE c.status
                    WHEN 'offline' THEN 0
                    WHEN 'warning' THEN 1
                    WHEN 'never' THEN 2
                    WHEN 'healthy' THEN 3
                    ELSE 4
                END, c.name
                """
            ).fetchall()
        channels = [self.public_channel(row) for row in rows]
        if status and status != "all":
            channels = [item for item in channels if item["status"] == status]
        return channels

    def get_channel_row(self, channel_id: int) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone()

    def list_channel_accounts(self, status: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM channels
                ORDER BY
                    CASE WHEN source_channel_id IS NULL THEN id ELSE source_channel_id END,
                    CASE WHEN source_channel_id IS NULL THEN 0 ELSE 1 END,
                    is_default_key DESC,
                    name COLLATE NOCASE
                """
            ).fetchall()
        by_parent: dict[int, list[sqlite3.Row]] = {}
        root_rows: list[sqlite3.Row] = []
        for row in rows:
            parent_id = row["source_channel_id"]
            if parent_id is None:
                root_rows.append(row)
            else:
                by_parent.setdefault(int(parent_id), []).append(row)

        accounts: list[dict[str, Any]] = []
        for row in root_rows:
            children = by_parent.get(int(row["id"]), [])
            if not children and not self.is_account_parent_row(row):
                children = [row]
            public_children = [self.public_channel(child) for child in children]
            if status and status != "all":
                public_children = [item for item in public_children if item["status"] == status]
            if status and status != "all" and not public_children:
                continue
            if len(public_children) == 1 and public_children[0]["id"] == row["id"] and not public_children[0].get("is_default_key"):
                public_children[0]["is_default_key"] = True
                public_children[0]["isDefaultKey"] = True
            parent = self.public_channel(row)
            parent["children"] = public_children
            parent["child_count"] = len(public_children)
            parent["childCount"] = len(public_children)
            parent["monitoring_count"] = sum(1 for item in public_children if item.get("is_monitoring") or item.get("isMonitoring"))
            parent["monitoringCount"] = parent["monitoring_count"]
            parent["default_child_id"] = next((item["id"] for item in public_children if item.get("is_default_key") or item.get("isDefaultKey")), None)
            parent["defaultChildId"] = parent["default_child_id"]
            accounts.append(parent)
        return accounts

    def public_channel(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        masked_key = data.get("api_key_masked")
        secret = data.get("api_key") or masked_key or data.get("access_token") or data.get("refresh_token")
        status = data.get("status") or "never"
        balance = optional_float(data.get("balance"))
        threshold = optional_float(data.get("threshold")) or 0
        quota_total = optional_float(data.get("quota_total"))
        if quota_total is not None and quota_total > 0 and balance is not None:
            remaining_percent = max(0, min(100, balance / quota_total * 100))
        elif balance is not None and threshold > 0:
            remaining_percent = max(0, min(100, balance / (threshold * 5) * 100))
        else:
            remaining_percent = 0 if status == "offline" else 35
        available_groups = self.list_channel_groups(data["id"])
        return {
            "id": data["id"],
            "name": data["name"],
            "platform": data["platform"],
            "base_url": data["base_url"],
            "baseUrl": data["base_url"],
            "model_scope": data.get("model_scope") or "All models",
            "modelScope": data.get("model_scope") or "All models",
            "group_id": data.get("group_id"),
            "groupId": data.get("group_id"),
            "group_name": data.get("group_name") or data.get("group_id") or "未选择分组",
            "groupName": data.get("group_name") or data.get("group_id") or "未选择分组",
            "rate_multiplier": data.get("rate_multiplier"),
            "rateMultiplier": data.get("rate_multiplier"),
            "external_key_id": data.get("external_key_id"),
            "externalKeyId": data.get("external_key_id"),
            "key_name": data.get("key_name"),
            "keyName": data.get("key_name"),
            "key_provider": data.get("key_provider"),
            "keyProvider": data.get("key_provider"),
            "api_key_masked": masked_key,
            "apiKeyMasked": masked_key,
            "source_channel_id": data.get("source_channel_id"),
            "sourceChannelId": data.get("source_channel_id"),
            "parent_name": data.get("parent_name"),
            "parentName": data.get("parent_name"),
            "threshold": threshold,
            "balance": balance,
            "unit": data.get("unit") or "USD",
            "quota_total": quota_total,
            "quotaTotal": quota_total,
            "used": data.get("used"),
            "status": status,
            "last_error": data.get("last_error"),
            "lastError": data.get("last_error"),
            "last_checked_at": data.get("last_checked_at"),
            "lastCheckedAt": data.get("last_checked_at"),
            "is_enabled": bool(data.get("is_enabled")),
            "isEnabled": bool(data.get("is_enabled")),
            "is_demo": bool(data.get("is_demo")),
            "isDemo": bool(data.get("is_demo")),
            "is_account_parent": bool(data.get("is_account_parent")),
            "isAccountParent": bool(data.get("is_account_parent")),
            "is_default_key": bool(data.get("is_default_key")),
            "isDefaultKey": bool(data.get("is_default_key")),
            "is_monitoring": bool(data.get("is_monitoring")),
            "isMonitoring": bool(data.get("is_monitoring")),
            "monitor_models": self.monitor_models_for_provider(data.get("key_provider"), data.get("monitor_models")),
            "monitorModels": self.monitor_models_for_provider(data.get("key_provider"), data.get("monitor_models")),
            "monitor_interval_seconds": int(data.get("monitor_interval_seconds") or 60),
            "monitorIntervalSeconds": int(data.get("monitor_interval_seconds") or 60),
            "monitor_status": data.get("monitor_status") or "idle",
            "monitorStatus": data.get("monitor_status") or "idle",
            "monitor_last_checked_at": data.get("monitor_last_checked_at"),
            "monitorLastCheckedAt": data.get("monitor_last_checked_at"),
            "monitor_last_error": data.get("monitor_last_error"),
            "monitorLastError": data.get("monitor_last_error"),
            "monitor_latency_ms": data.get("monitor_latency_ms"),
            "monitorLatencyMs": data.get("monitor_latency_ms"),
            "monitor_result": self.monitor_result(data.get("monitor_result_json")),
            "monitorResult": self.monitor_result(data.get("monitor_result_json")),
            "key_masked": masked_key or mask_secret(secret),
            "keyMasked": masked_key or mask_secret(secret),
            "has_api_key": bool(data.get("api_key")),
            "hasApiKey": bool(data.get("api_key")),
            "has_access_token": bool(data.get("access_token")),
            "hasAccessToken": bool(data.get("access_token")),
            "remaining_percent": round(remaining_percent, 2),
            "remainingPercent": round(remaining_percent, 2),
            "created_at": data.get("created_at"),
            "createdAt": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "updatedAt": data.get("updated_at"),
            "available_groups": available_groups,
            "availableGroups": available_groups,
        }

    def is_account_parent_row(self, row: sqlite3.Row) -> bool:
        return bool(row["is_account_parent"]) or self.is_sync_shell_channel(row)

    def monitor_models(self, value: Any) -> list[str]:
        if isinstance(value, list):
            models = value
        else:
            try:
                models = json.loads(value) if value else DEFAULT_MONITOR_MODELS
            except (TypeError, json.JSONDecodeError):
                models = str(value or "").split(",")
        result = [str(model).strip() for model in models if str(model).strip()]
        return result or DEFAULT_MONITOR_MODELS.copy()

    def monitor_models_for_provider(self, provider: Any, value: Any = None) -> list[str]:
        normalized_provider = normalize_key_provider(provider)
        models = self.monitor_models(value)
        if normalized_provider == "openai":
            filtered = [model for model in models if self.is_openai_monitor_model(model)]
            return filtered or PROVIDER_MONITOR_MODELS["openai"].copy()
        if normalized_provider == "anthropic":
            filtered = [model for model in models if self.is_anthropic_monitor_model(model)]
            return filtered or PROVIDER_MONITOR_MODELS["anthropic"].copy()
        return models

    def default_monitor_models(self, provider: Any) -> list[str]:
        normalized_provider = normalize_key_provider(provider)
        if normalized_provider in PROVIDER_MONITOR_MODELS:
            return PROVIDER_MONITOR_MODELS[normalized_provider].copy()
        return DEFAULT_MONITOR_MODELS.copy()

    def is_openai_monitor_model(self, model: Any) -> bool:
        return "gpt" in str(model or "").strip().lower()

    def is_anthropic_monitor_model(self, model: Any) -> bool:
        return "claude" in str(model or "").strip().lower()

    def monitor_result(self, value: Any) -> dict[str, Any] | None:
        if not value:
            return None
        try:
            payload = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def list_channel_groups(self, channel_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM channel_groups
                WHERE channel_id = ?
                ORDER BY
                    CASE WHEN rate_multiplier IS NULL THEN 1 ELSE 0 END,
                    rate_multiplier ASC,
                    group_name COLLATE NOCASE,
                    group_id
                """,
                (channel_id,),
            ).fetchall()
        return [
            {
                **group_payload(row["payload_json"]),
                "group_id": row["group_id"],
                "groupId": row["group_id"],
                "group_name": row["group_name"] or row["group_id"],
                "groupName": row["group_name"] or row["group_id"],
                "rate_multiplier": row["rate_multiplier"],
                "rateMultiplier": row["rate_multiplier"],
                "updated_at": row["updated_at"],
                "updatedAt": row["updated_at"],
            }
            for row in rows
        ]

    def store_channel_groups(self, channel_id: int, groups: list[dict[str, Any]]) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute("DELETE FROM channel_groups WHERE channel_id = ?", (channel_id,))
            for group in groups:
                group_id = str(group.get("group_id") or group.get("groupId") or "").strip()
                if not group_id:
                    continue
                group_name = str(group.get("group_name") or group.get("groupName") or group_id).strip()
                conn.execute(
                    """
                    INSERT OR REPLACE INTO channel_groups (
                        channel_id, group_id, group_name, rate_multiplier, payload_json, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                (
                        channel_id,
                        group_id,
                        group_name,
                        optional_float(group.get("rate_multiplier"))
                        if group.get("rate_multiplier") is not None
                        else optional_float(group.get("rateMultiplier")),
                        json.dumps(group, ensure_ascii=False),
                        now,
                    ),
                )

    def create_channel(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("name") or "").strip()
        platform = str(payload.get("platform") or "").strip()
        base_url = normalize_base_url(payload.get("base_url") or payload.get("baseUrl"))
        api_key = str(payload.get("api_key") or payload.get("apiKey") or "").strip() or None
        access_token = str(payload.get("access_token") or payload.get("accessToken") or "").strip() or None
        refresh_token = str(payload.get("refresh_token") or payload.get("refreshToken") or "").strip() or None
        user_id = str(payload.get("user_id") or payload.get("userId") or "").strip() or None
        email = str(payload.get("email") or "").strip() or None
        password = str(payload.get("password") or "").strip() or None
        key_provider = normalize_key_provider(payload.get("key_provider") or payload.get("keyProvider") or payload.get("provider") or payload.get("type"))
        if not name:
            raise ApiError(400, "渠道名称不能为空")
        if platform not in {"newApi", "sub2Api"}:
            raise ApiError(400, "platform 必须是 newApi 或 sub2Api")
        if not base_url:
            raise ApiError(400, "Base URL 不能为空")
        if platform == "sub2Api" and not access_token and email and password:
            auth = login_sub2api_credentials(
                base_url,
                email,
                password,
                str(payload.get("turnstile_token") or payload.get("turnstileToken") or "").strip() or None,
            )
            access_token = auth.get("access_token") or access_token
            refresh_token = auth.get("refresh_token") or refresh_token
            user_id = auth.get("user_id") or user_id
        is_account_parent = platform == "sub2Api" and bool(email or password or access_token or refresh_token)
        parent_api_key = None if is_account_parent else api_key
        parent_key_masked = None if is_account_parent else str(payload.get("api_key_masked") or payload.get("apiKeyMasked") or "").strip() or None
        parent_external_key_id = None if is_account_parent else str(payload.get("external_key_id") or payload.get("externalKeyId") or "").strip() or None
        parent_key_name = None if is_account_parent else str(payload.get("key_name") or payload.get("keyName") or "").strip() or None
        parent_key_provider = None if is_account_parent else key_provider
        now = utc_now()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO channels (
                    name, platform, base_url, model_scope, group_id, group_name, rate_multiplier,
                    threshold, api_key, api_key_masked, access_token, refresh_token, user_id, email, password,
                    external_key_id, key_name, key_provider, source_channel_id, is_enabled, is_demo, is_account_parent,
                    is_default_key, monitor_models, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    platform,
                    base_url,
                    str(payload.get("model_scope") or payload.get("modelScope") or "All models").strip(),
                    str(payload.get("group_id") or payload.get("groupId") or "").strip() or None,
                    str(payload.get("group_name") or payload.get("groupName") or "").strip() or None,
                    optional_float(payload.get("rate_multiplier") or payload.get("rateMultiplier")),
                    optional_float(payload.get("threshold")) or 10,
                    parent_api_key,
                    parent_key_masked,
                    access_token,
                    refresh_token,
                    user_id,
                    email,
                    password,
                    parent_external_key_id,
                    parent_key_name,
                    parent_key_provider,
                    int(payload.get("source_channel_id") or payload.get("sourceChannelId"))
                    if (payload.get("source_channel_id") or payload.get("sourceChannelId"))
                    else None,
                    1 if bool_value(payload.get("is_enabled", payload.get("isEnabled", True))) else 0,
                    1 if bool_value(payload.get("is_demo", payload.get("isDemo", False))) else 0,
                    1 if is_account_parent else 0,
                    0 if is_account_parent else 1 if bool_value(payload.get("is_default_key", payload.get("isDefaultKey", False))) else 0,
                    json.dumps(
                        self.monitor_models_for_provider(
                            parent_key_provider,
                            payload.get("monitor_models") or payload.get("monitorModels"),
                        ),
                        ensure_ascii=False,
                    ),
                    now,
                    now,
                ),
            )
            channel_id = int(cursor.lastrowid)
            if is_account_parent and api_key:
                conn.execute(
                    """
                    INSERT INTO channels (
                        name, platform, base_url, model_scope, group_id, group_name, rate_multiplier,
                        threshold, api_key, api_key_masked, access_token, refresh_token, user_id, email, password,
                        external_key_id, key_name, key_provider, source_channel_id, is_enabled, is_demo, is_account_parent,
                        is_default_key, monitor_models, status, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?, 'never', ?, ?)
                    """,
                    (
                        str(payload.get("key_name") or payload.get("keyName") or name).strip() or name,
                        platform,
                        base_url,
                        str(payload.get("model_scope") or payload.get("modelScope") or "All models").strip(),
                        str(payload.get("group_id") or payload.get("groupId") or "").strip() or None,
                        str(payload.get("group_name") or payload.get("groupName") or "").strip() or None,
                        optional_float(payload.get("rate_multiplier") or payload.get("rateMultiplier")),
                        optional_float(payload.get("threshold")) or 10,
                        api_key,
                        str(payload.get("api_key_masked") or payload.get("apiKeyMasked") or "").strip() or mask_secret(api_key),
                        access_token,
                        refresh_token,
                        user_id,
                        email,
                        password,
                        str(payload.get("external_key_id") or payload.get("externalKeyId") or "").strip() or None,
                        str(payload.get("key_name") or payload.get("keyName") or "").strip() or None,
                        key_provider,
                        channel_id,
                        1 if bool_value(payload.get("is_enabled", payload.get("isEnabled", True))) else 0,
                        1 if bool_value(payload.get("is_demo", payload.get("isDemo", False))) else 0,
                        json.dumps(
                            self.monitor_models_for_provider(
                                key_provider,
                                payload.get("monitor_models") or payload.get("monitorModels"),
                            ),
                            ensure_ascii=False,
                        ),
                        now,
                        now,
                    ),
                )
        return self.public_channel(self.get_channel_row(channel_id))

    def update_channel(self, channel_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        row = self.get_channel_row(channel_id)
        if not row:
            raise ApiError(404, "渠道不存在")
        allowed = {
            "name": "name",
            "platform": "platform",
            "base_url": "base_url",
            "baseUrl": "base_url",
            "model_scope": "model_scope",
            "modelScope": "model_scope",
            "group_id": "group_id",
            "groupId": "group_id",
            "group_name": "group_name",
            "groupName": "group_name",
            "rate_multiplier": "rate_multiplier",
            "rateMultiplier": "rate_multiplier",
            "threshold": "threshold",
            "api_key": "api_key",
            "apiKey": "api_key",
            "api_key_masked": "api_key_masked",
            "apiKeyMasked": "api_key_masked",
            "access_token": "access_token",
            "accessToken": "access_token",
            "refresh_token": "refresh_token",
            "refreshToken": "refresh_token",
            "user_id": "user_id",
            "userId": "user_id",
            "email": "email",
            "password": "password",
            "external_key_id": "external_key_id",
            "externalKeyId": "external_key_id",
            "key_name": "key_name",
            "keyName": "key_name",
            "key_provider": "key_provider",
            "keyProvider": "key_provider",
            "source_channel_id": "source_channel_id",
            "sourceChannelId": "source_channel_id",
            "is_enabled": "is_enabled",
            "isEnabled": "is_enabled",
            "is_demo": "is_demo",
            "isDemo": "is_demo",
            "is_account_parent": "is_account_parent",
            "isAccountParent": "is_account_parent",
            "is_default_key": "is_default_key",
            "isDefaultKey": "is_default_key",
            "is_monitoring": "is_monitoring",
            "isMonitoring": "is_monitoring",
            "monitor_models": "monitor_models",
            "monitorModels": "monitor_models",
            "monitor_interval_seconds": "monitor_interval_seconds",
            "monitorIntervalSeconds": "monitor_interval_seconds",
        }
        assignments: list[str] = []
        params: list[Any] = []
        should_set_default = False
        next_key_provider: str | None = None
        for key, column in allowed.items():
            if key not in payload:
                continue
            value = payload[key]
            if column == "base_url":
                value = normalize_base_url(value)
            elif column in {"threshold", "rate_multiplier"}:
                value = optional_float(value)
            elif column == "source_channel_id":
                value = int(value) if value not in {None, ""} else None
            elif column in {"is_enabled", "is_account_parent", "is_monitoring"}:
                value = 1 if bool_value(value) else 0
            elif column == "is_default_key":
                should_set_default = bool_value(value)
                value = 1 if should_set_default else 0
            elif column == "is_demo":
                value = 1 if bool_value(value) else 0
            elif column == "monitor_models":
                value = json.dumps(self.monitor_models_for_provider(payload.get("key_provider") or payload.get("keyProvider") or row["key_provider"], value), ensure_ascii=False)
            elif column == "monitor_interval_seconds":
                try:
                    value = max(15, int(value or 60))
                except (TypeError, ValueError) as exc:
                    raise ApiError(400, "monitor_interval_seconds 必须是数字") from exc
            elif column == "key_provider":
                value = normalize_key_provider(value)
                next_key_provider = value
            elif isinstance(value, str):
                value = value.strip() or None
            assignments.append(f"{column} = ?")
            params.append(value)
        if next_key_provider and "monitor_models" not in payload and "monitorModels" not in payload:
            assignments.append("monitor_models = ?")
            params.append(json.dumps(self.monitor_models_for_provider(next_key_provider, row["monitor_models"]), ensure_ascii=False))
        if assignments:
            assignments.append("updated_at = ?")
            params.append(utc_now())
            params.append(channel_id)
            with self.connect() as conn:
                conn.execute(f"UPDATE channels SET {', '.join(assignments)} WHERE id = ?", tuple(params))
        if should_set_default:
            self.set_default_key(channel_id)
        return self.public_channel(self.get_channel_row(channel_id))

    def set_default_key(self, channel_id: int) -> None:
        row = self.get_channel_row(channel_id)
        if not row:
            raise ApiError(404, "渠道不存在")
        parent_id = row["source_channel_id"] or row["id"]
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE channels
                SET is_default_key = 0, updated_at = ?
                WHERE source_channel_id = ? OR id = ?
                """,
                (utc_now(), parent_id, parent_id),
            )
            conn.execute(
                """
                UPDATE channels
                SET is_default_key = 1, updated_at = ?
                WHERE id = ?
                """,
                (utc_now(), channel_id),
            )

    def delete_channel(self, channel_id: int) -> None:
        with self.connect() as conn:
            cursor = conn.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
            if cursor.rowcount == 0:
                raise ApiError(404, "渠道不存在")

    def enabled_channel_ids(self) -> list[int]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT c.id
                FROM channels c
                WHERE c.is_enabled = 1
                  AND c.source_channel_id IS NULL
                ORDER BY c.id
                """
            ).fetchall()
        return [int(row["id"]) for row in rows]

    def is_sync_shell_channel(self, row: sqlite3.Row) -> bool:
        return (
            row["platform"] == "sub2Api"
            and not row["api_key"]
            and not row["external_key_id"]
            and bool(row["access_token"] or row["refresh_token"] or row["email"])
        )

    def upsert_synced_keys(
        self,
        parent_row: sqlite3.Row,
        keys: list[dict[str, Any]],
        groups: list[dict[str, Any]],
    ) -> list[int]:
        imported_ids: list[int] = []
        parent_id = int(parent_row["id"])
        parent_name = str(parent_row["name"] or "渠道")
        base_url = parent_row["base_url"]
        platform = parent_row["platform"]
        now = utc_now()
        with self.connect() as conn:
            for key in keys:
                external_key_id = str(key.get("external_key_id") or key.get("externalKeyId") or "").strip() or None
                api_key = str(key.get("api_key") or key.get("apiKey") or "").strip() or None
                masked_key = str(key.get("api_key_masked") or key.get("apiKeyMasked") or key.get("key_masked") or key.get("keyMasked") or "").strip() or None
                key_provider = normalize_key_provider(key.get("key_provider") or key.get("keyProvider") or key.get("provider") or key.get("type"))
                if not external_key_id and not api_key and not masked_key:
                    continue

                target_id: int | None = None
                if external_key_id:
                    existing = conn.execute(
                        """
                        SELECT id FROM channels
                        WHERE platform = ? AND base_url = ? AND external_key_id = ?
                        LIMIT 1
                        """,
                        (platform, base_url, external_key_id),
                    ).fetchone()
                    target_id = int(existing["id"]) if existing else None
                if target_id is None and not self.is_account_parent_row(parent_row) and imported_key_matches_channel(parent_row, key):
                    target_id = parent_id
                if target_id is None and api_key:
                    existing = conn.execute(
                        """
                        SELECT id FROM channels
                        WHERE platform = ? AND base_url = ? AND api_key = ?
                        LIMIT 1
                        """,
                        (platform, base_url, api_key),
                    ).fetchone()
                    target_id = int(existing["id"]) if existing else None

                key_group_id = key.get("group_id") or key.get("groupId") or parent_row["group_id"]
                selected = find_group(groups, key_group_id) or find_group(groups, parent_row["group_id"]) or (groups[0] if groups else None)
                group_id = (selected.get("group_id") if selected else key_group_id) or None
                group_name = (selected.get("group_name") if selected else key.get("group_name") or key.get("groupName") or group_id) or None
                if key_provider is None and selected:
                    key_provider = normalize_key_provider(
                        selected.get("platform")
                        or selected.get("provider")
                        or selected.get("provider_type")
                        or selected.get("providerType")
                        or selected.get("type")
                        or selected.get("group_name")
                        or selected.get("groupName")
                    )
                rate = optional_float(selected.get("rate_multiplier")) if selected else None
                key_name = str(key.get("key_name") or key.get("keyName") or "").strip() or None
                model_scope = str(key.get("model_scope") or key.get("modelScope") or parent_row["model_scope"] or "All models").strip()
                is_enabled = 1 if bool_value(key.get("is_enabled", key.get("isEnabled", True))) else 0
                monitor_models = self.monitor_models_for_provider(key_provider, key.get("monitor_models") or key.get("monitorModels"))
                monitor_models_json = json.dumps(monitor_models, ensure_ascii=False)
                default_monitor_models_json = json.dumps(DEFAULT_MONITOR_MODELS, ensure_ascii=False)

                if target_id is not None:
                    if target_id == parent_id:
                        channel_name = key_name or parent_name
                    else:
                        channel_name = key_name or f"{parent_name} #{external_key_id or target_id}"
                    source_channel_id = parent_row["source_channel_id"] if target_id == parent_id else parent_id
                    conn.execute(
                        """
                        UPDATE channels
                        SET name = ?,
                            model_scope = ?,
                            group_id = ?,
                            group_name = ?,
                            rate_multiplier = COALESCE(?, rate_multiplier),
                            api_key = COALESCE(?, api_key),
                            api_key_masked = COALESCE(?, api_key_masked),
                            access_token = COALESCE(?, access_token),
                            refresh_token = COALESCE(?, refresh_token),
                            user_id = COALESCE(?, user_id),
                            email = COALESCE(?, email),
                            password = COALESCE(?, password),
                            external_key_id = COALESCE(?, external_key_id),
                            key_name = COALESCE(?, key_name),
                            key_provider = COALESCE(?, key_provider),
                            source_channel_id = ?,
                            is_enabled = ?,
                            is_demo = 0,
                            is_account_parent = CASE WHEN id = ? THEN is_account_parent ELSE 0 END,
                            monitor_models = CASE
                                WHEN ? IS NULL THEN monitor_models
                                WHEN monitor_models IS NULL OR monitor_models = ? THEN ?
                                ELSE monitor_models
                            END,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            channel_name,
                            model_scope,
                            group_id,
                            group_name,
                            rate,
                            api_key,
                            masked_key,
                            parent_row["access_token"],
                            parent_row["refresh_token"],
                            parent_row["user_id"],
                            parent_row["email"],
                            parent_row["password"],
                            external_key_id,
                            key_name,
                            key_provider,
                            source_channel_id,
                            is_enabled,
                            parent_id,
                            key_provider,
                            default_monitor_models_json,
                            monitor_models_json,
                            now,
                            target_id,
                        ),
                    )
                else:
                    channel_name = key_name or f"{parent_name} #{external_key_id or len(imported_ids) + 1}"
                    cursor = conn.execute(
                        """
                        INSERT INTO channels (
                            name, platform, base_url, model_scope, group_id, group_name, rate_multiplier,
                            threshold, api_key, api_key_masked, access_token, refresh_token, user_id, email,
                            password, external_key_id, key_name, key_provider, source_channel_id, is_enabled, is_demo,
                            is_account_parent, is_default_key, monitor_models, status, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, 'never', ?, ?)
                        """,
                        (
                            channel_name,
                            platform,
                            base_url,
                            model_scope,
                            group_id,
                            group_name,
                            rate,
                            optional_float(parent_row["threshold"]) or 10,
                            api_key,
                            masked_key,
                            parent_row["access_token"],
                            parent_row["refresh_token"],
                            parent_row["user_id"],
                            parent_row["email"],
                            parent_row["password"],
                            external_key_id,
                            key_name,
                            key_provider,
                            parent_id,
                            is_enabled,
                            monitor_models_json,
                            now,
                            now,
                        ),
                    )
                    target_id = int(cursor.lastrowid)
                if target_id not in imported_ids:
                    imported_ids.append(target_id)
            if imported_ids:
                placeholders = ", ".join("?" for _ in imported_ids)
                conn.execute(
                    f"""
                    DELETE FROM channels
                    WHERE source_channel_id = ?
                      AND id NOT IN ({placeholders})
                    """,
                    (parent_id, *imported_ids),
                )
            else:
                conn.execute(
                    """
                    DELETE FROM channels
                    WHERE source_channel_id = ?
                    """,
                    (parent_id,),
                )
            if imported_ids:
                existing_default = conn.execute(
                    """
                    SELECT id
                    FROM channels
                    WHERE (source_channel_id = ? OR id = ?)
                      AND is_default_key = 1
                    LIMIT 1
                    """,
                    (parent_id, parent_id),
                ).fetchone()
                if not existing_default:
                    conn.execute("UPDATE channels SET is_default_key = 1, updated_at = ? WHERE id = ?", (now, imported_ids[0]))
        return imported_ids
