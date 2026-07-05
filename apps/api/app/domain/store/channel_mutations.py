from __future__ import annotations

import json
from typing import Any

from apps.api.app.core.errors import ApiError
from apps.api.app.core.utils import bool_value, mask_secret, normalize_base_url, optional_float, utc_now
from apps.api.app.infrastructure.integrations import login_sub2api_credentials, normalize_key_provider


class ChannelMutationMixin:
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
        row = self.get_channel_row(channel_id)
        if not row:
            raise ApiError(404, "渠道不存在")
        with self.connect() as conn:
            conn.execute("DELETE FROM channels WHERE source_channel_id = ?", (channel_id,))
            cursor = conn.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
            if cursor.rowcount == 0:
                raise ApiError(404, "渠道不存在")
