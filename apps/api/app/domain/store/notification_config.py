from __future__ import annotations

from typing import Any

from apps.api.app.core.errors import ApiError
from apps.api.app.core.utils import bool_value, mask_secret

from .notification_constants import (
    NOTIFICATION_CHANNELS,
    PUSHPLUS_CHANNELS,
    PUSHPLUS_TEMPLATES,
    QQBOT_TARGET_LABELS,
    QQBOT_TARGET_TYPES,
)


class NotificationConfigMixin:
    notification_defaults = {
        "notification_enabled": "0",
        "notification_channel": "pushplus",
        "pushplus_enabled": "0",
        "pushplus_token": "",
        "pushplus_channel": "wechat",
        "pushplus_template": "markdown",
        "serverchan_enabled": "0",
        "serverchan_send_key": "",
        "qqbot_enabled": "0",
        "qqbot_app_id": "",
        "qqbot_client_secret": "",
        "qqbot_bot_secret": "",
        "qqbot_target_type": "subscribers",
        "qqbot_target_id": "",
        "qqbot_access_token": "",
        "qqbot_access_token_expires_at": "0",
        "qqbot_gateway_status": "stopped",
        "qqbot_gateway_last_error": "",
        "qqbot_gateway_last_connected_at": "",
        "qqbot_gateway_session_id": "",
        "qqbot_gateway_seq": "",
        "qqbot_last_event_type": "",
        "qqbot_last_target_type": "",
        "qqbot_last_target_id": "",
        "qqbot_last_event_at": "",
        "notify_low_balance": "1",
        "notify_rate_change": "1",
        "notify_model_failure": "1",
        "notify_pool_schedule": "1",
    }

    def notification_settings(self, *, include_secret: bool = False) -> dict[str, Any]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT key, value, updated_at
                FROM app_settings
                WHERE key IN (
                  'pushplus_enabled',
                  'notification_enabled',
                  'notification_channel',
                  'pushplus_token',
                  'pushplus_channel',
                  'pushplus_template',
                  'serverchan_enabled',
                  'serverchan_send_key',
                  'qqbot_enabled',
                  'qqbot_app_id',
                  'qqbot_client_secret',
                  'qqbot_bot_secret',
                  'qqbot_target_type',
                  'qqbot_target_id',
                  'qqbot_access_token',
                  'qqbot_access_token_expires_at',
                  'qqbot_gateway_status',
                  'qqbot_gateway_last_error',
                  'qqbot_gateway_last_connected_at',
                  'qqbot_gateway_session_id',
                  'qqbot_gateway_seq',
                  'qqbot_last_event_type',
                  'qqbot_last_target_type',
                  'qqbot_last_target_id',
                  'qqbot_last_event_at',
                  'notify_low_balance',
                  'notify_rate_change',
                  'notify_model_failure',
                  'notify_pool_schedule'
                )
                """
            ).fetchall()
            subscriber_rows = conn.execute(
                """
                SELECT target_type, target_id, source_event, created_at, last_seen_at
                FROM qqbot_subscribers
                WHERE is_enabled = 1
                ORDER BY last_seen_at DESC
                LIMIT 5
                """
            ).fetchall()
            subscriber_count = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM qqbot_subscribers
                WHERE is_enabled = 1
                """
            ).fetchone()["count"]
        values = self.notification_defaults.copy()
        updated_at = None
        stored_keys: set[str] = set()
        for row in rows:
            stored_keys.add(row["key"])
            values[row["key"]] = row["value"] or ""
            updated_at = max(updated_at or row["updated_at"], row["updated_at"])

        token = values["pushplus_token"].strip()
        send_key = values["serverchan_send_key"].strip()
        qqbot_app_id = values["qqbot_app_id"].strip()
        qqbot_client_secret = values["qqbot_client_secret"].strip()
        qqbot_bot_secret = values["qqbot_bot_secret"].strip()
        qqbot_secret = qqbot_client_secret or qqbot_bot_secret
        qqbot_target_type = values["qqbot_target_type"] if values["qqbot_target_type"] in QQBOT_TARGET_TYPES else "subscribers"
        qqbot_target_id = values["qqbot_target_id"].strip()
        qqbot_uses_subscribers = qqbot_target_type == "subscribers"
        qqbot_configured = bool(qqbot_app_id and qqbot_secret and (qqbot_target_id or qqbot_uses_subscribers))
        qqbot_recent_subscribers = [
            {
                "target_type": row["target_type"],
                "targetType": row["target_type"],
                "target_label": QQBOT_TARGET_LABELS.get(row["target_type"], "QQBot"),
                "targetLabel": QQBOT_TARGET_LABELS.get(row["target_type"], "QQBot"),
                "target_id_masked": mask_secret(row["target_id"]),
                "targetIdMasked": mask_secret(row["target_id"]),
                "source_event": row["source_event"],
                "sourceEvent": row["source_event"],
                "created_at": row["created_at"],
                "createdAt": row["created_at"],
                "last_seen_at": row["last_seen_at"],
                "lastSeenAt": row["last_seen_at"],
            }
            for row in subscriber_rows
        ]
        legacy_enabled = bool_value(values["pushplus_enabled"]) or bool_value(values["serverchan_enabled"]) or bool_value(values["qqbot_enabled"])
        enabled = bool_value(values["notification_enabled"]) if "notification_enabled" in stored_keys else legacy_enabled
        channel = values["notification_channel"] if values["notification_channel"] in NOTIFICATION_CHANNELS else ""
        if not channel:
            if bool_value(values["pushplus_enabled"]):
                channel = "pushplus"
            elif bool_value(values["serverchan_enabled"]):
                channel = "serverchan"
            elif bool_value(values["qqbot_enabled"]):
                channel = "qqbot"
            else:
                channel = "pushplus"
        result = {
            "notification_enabled": enabled,
            "notificationEnabled": enabled,
            "notification_channel": channel,
            "notificationChannel": channel,
            "pushplus_enabled": enabled and channel == "pushplus",
            "pushplusEnabled": enabled and channel == "pushplus",
            "pushplus_configured": bool(token),
            "pushplusConfigured": bool(token),
            "pushplus_token_masked": mask_secret(token),
            "pushplusTokenMasked": mask_secret(token),
            "pushplus_channel": values["pushplus_channel"] if values["pushplus_channel"] in PUSHPLUS_CHANNELS else "wechat",
            "pushplusChannel": values["pushplus_channel"] if values["pushplus_channel"] in PUSHPLUS_CHANNELS else "wechat",
            "pushplus_template": values["pushplus_template"] if values["pushplus_template"] in PUSHPLUS_TEMPLATES else "markdown",
            "pushplusTemplate": values["pushplus_template"] if values["pushplus_template"] in PUSHPLUS_TEMPLATES else "markdown",
            "serverchan_enabled": enabled and channel == "serverchan",
            "serverchanEnabled": enabled and channel == "serverchan",
            "serverchan_configured": bool(send_key),
            "serverchanConfigured": bool(send_key),
            "serverchan_send_key_masked": mask_secret(send_key),
            "serverchanSendKeyMasked": mask_secret(send_key),
            "qqbot_enabled": enabled and channel == "qqbot",
            "qqbotEnabled": enabled and channel == "qqbot",
            "qqbot_configured": qqbot_configured,
            "qqbotConfigured": qqbot_configured,
            "qqbot_webhook_configured": bool(qqbot_secret),
            "qqbotWebhookConfigured": bool(qqbot_secret),
            "qqbot_app_id": qqbot_app_id,
            "qqbotAppId": qqbot_app_id,
            "qqbot_secret_masked": mask_secret(qqbot_secret),
            "qqbotSecretMasked": mask_secret(qqbot_secret),
            "qqbot_client_secret_masked": mask_secret(qqbot_client_secret),
            "qqbotClientSecretMasked": mask_secret(qqbot_client_secret),
            "qqbot_bot_secret_masked": mask_secret(qqbot_bot_secret),
            "qqbotBotSecretMasked": mask_secret(qqbot_bot_secret),
            "qqbot_target_type": qqbot_target_type,
            "qqbotTargetType": qqbot_target_type,
            "qqbot_target_label": QQBOT_TARGET_LABELS.get(qqbot_target_type, "QQBot"),
            "qqbotTargetLabel": QQBOT_TARGET_LABELS.get(qqbot_target_type, "QQBot"),
            "qqbot_target_id": qqbot_target_id,
            "qqbotTargetId": qqbot_target_id,
            "qqbot_target_id_masked": mask_secret(qqbot_target_id),
            "qqbotTargetIdMasked": mask_secret(qqbot_target_id),
            "qqbot_transport": "websocket",
            "qqbotTransport": "websocket",
            "qqbot_gateway_status": values["qqbot_gateway_status"] or "stopped",
            "qqbotGatewayStatus": values["qqbot_gateway_status"] or "stopped",
            "qqbot_gateway_last_error": values["qqbot_gateway_last_error"],
            "qqbotGatewayLastError": values["qqbot_gateway_last_error"],
            "qqbot_gateway_last_connected_at": values["qqbot_gateway_last_connected_at"],
            "qqbotGatewayLastConnectedAt": values["qqbot_gateway_last_connected_at"],
            "qqbot_gateway_seq": values["qqbot_gateway_seq"],
            "qqbotGatewaySeq": values["qqbot_gateway_seq"],
            "qqbot_subscriber_count": subscriber_count,
            "qqbotSubscriberCount": subscriber_count,
            "qqbot_recent_subscribers": qqbot_recent_subscribers,
            "qqbotRecentSubscribers": qqbot_recent_subscribers,
            "qqbot_last_event_type": values["qqbot_last_event_type"],
            "qqbotLastEventType": values["qqbot_last_event_type"],
            "qqbot_last_target_type": values["qqbot_last_target_type"],
            "qqbotLastTargetType": values["qqbot_last_target_type"],
            "qqbot_last_target_id": values["qqbot_last_target_id"],
            "qqbotLastTargetId": values["qqbot_last_target_id"],
            "qqbot_last_target_id_masked": mask_secret(values["qqbot_last_target_id"]),
            "qqbotLastTargetIdMasked": mask_secret(values["qqbot_last_target_id"]),
            "qqbot_last_event_at": values["qqbot_last_event_at"],
            "qqbotLastEventAt": values["qqbot_last_event_at"],
            "notify_low_balance": bool_value(values["notify_low_balance"]),
            "notifyLowBalance": bool_value(values["notify_low_balance"]),
            "notify_pool_schedule": bool_value(values["notify_pool_schedule"]),
            "notifyPoolSchedule": bool_value(values["notify_pool_schedule"]),
            "notify_rate_change": bool_value(values["notify_rate_change"]),
            "notifyRateChange": bool_value(values["notify_rate_change"]),
            "notify_model_failure": bool_value(values["notify_model_failure"]),
            "notifyModelFailure": bool_value(values["notify_model_failure"]),
            "updated_at": updated_at,
            "updatedAt": updated_at,
        }
        if include_secret:
            result["pushplus_token"] = token
            result["pushplusToken"] = token
            result["serverchan_send_key"] = send_key
            result["serverchanSendKey"] = send_key
            result["qqbot_secret"] = qqbot_secret
            result["qqbotSecret"] = qqbot_secret
            result["qqbot_client_secret"] = qqbot_client_secret
            result["qqbotClientSecret"] = qqbot_client_secret
            result["qqbot_bot_secret"] = qqbot_bot_secret
            result["qqbotBotSecret"] = qqbot_bot_secret
            result["qqbot_access_token"] = values["qqbot_access_token"].strip()
            result["qqbotAccessToken"] = values["qqbot_access_token"].strip()
            result["qqbot_access_token_expires_at"] = values["qqbot_access_token_expires_at"].strip()
            result["qqbotAccessTokenExpiresAt"] = values["qqbot_access_token_expires_at"].strip()
            result["qqbot_gateway_session_id"] = values["qqbot_gateway_session_id"].strip()
            result["qqbotGatewaySessionId"] = values["qqbot_gateway_session_id"].strip()
        return result

    def update_notification_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.notification_settings(include_secret=True)
        updates: dict[str, str] = {}
        bool_fields = {
            "notification_enabled": ("notification_enabled", "notificationEnabled"),
            "notify_low_balance": ("notify_low_balance", "notifyLowBalance"),
            "notify_rate_change": ("notify_rate_change", "notifyRateChange"),
            "notify_model_failure": ("notify_model_failure", "notifyModelFailure"),
            "notify_pool_schedule": ("notify_pool_schedule", "notifyPoolSchedule"),
        }
        for target, keys in bool_fields.items():
            value = self.payload_value(payload, *keys)
            if value is not None:
                updates[target] = "1" if bool_value(value) else "0"

        notification_channel = self.payload_value(payload, "notification_channel", "notificationChannel")
        if notification_channel is not None:
            normalized = str(notification_channel or "pushplus").strip().lower()
            if normalized not in NOTIFICATION_CHANNELS:
                raise ApiError(400, "通知通道不支持")
            updates["notification_channel"] = normalized
            updates["pushplus_enabled"] = "1" if normalized == "pushplus" and bool_value(updates.get("notification_enabled", current.get("notification_enabled"))) else "0"
            updates["serverchan_enabled"] = "1" if normalized == "serverchan" and bool_value(updates.get("notification_enabled", current.get("notification_enabled"))) else "0"
            updates["qqbot_enabled"] = "1" if normalized == "qqbot" and bool_value(updates.get("notification_enabled", current.get("notification_enabled"))) else "0"

        legacy_pushplus_enabled = self.payload_value(payload, "pushplus_enabled", "pushplusEnabled")
        legacy_serverchan_enabled = self.payload_value(payload, "serverchan_enabled", "serverchanEnabled")
        if legacy_pushplus_enabled is not None or legacy_serverchan_enabled is not None:
            pushplus_enabled = bool_value(legacy_pushplus_enabled)
            serverchan_enabled = bool_value(legacy_serverchan_enabled)
            if serverchan_enabled and not pushplus_enabled:
                updates["notification_channel"] = "serverchan"
                updates["notification_enabled"] = "1"
            elif pushplus_enabled:
                updates["notification_channel"] = "pushplus"
                updates["notification_enabled"] = "1"
            elif not pushplus_enabled and not serverchan_enabled:
                updates["notification_enabled"] = "0"

        token = self.payload_value(payload, "pushplus_token", "pushplusToken")
        if token is not None and str(token).strip():
            updates["pushplus_token"] = str(token).strip()
        if bool_value(self.payload_value(payload, "clear_pushplus_token", "clearPushplusToken")):
            updates["pushplus_token"] = ""

        send_key = self.payload_value(payload, "serverchan_send_key", "serverchanSendKey")
        if send_key is not None and str(send_key).strip():
            updates["serverchan_send_key"] = str(send_key).strip()
        if bool_value(self.payload_value(payload, "clear_serverchan_send_key", "clearServerchanSendKey")):
            updates["serverchan_send_key"] = ""

        channel = self.payload_value(payload, "pushplus_channel", "pushplusChannel")
        if channel is not None:
            normalized = str(channel or "wechat").strip().lower()
            if normalized not in PUSHPLUS_CHANNELS:
                raise ApiError(400, "pushplus channel 不支持")
            updates["pushplus_channel"] = normalized

        template = self.payload_value(payload, "pushplus_template", "pushplusTemplate")
        if template is not None:
            normalized = str(template or "markdown").strip().lower()
            if normalized not in PUSHPLUS_TEMPLATES:
                raise ApiError(400, "pushplus template 不支持")
            updates["pushplus_template"] = normalized

        qqbot_app_id = self.payload_value(payload, "qqbot_app_id", "qqbotAppId")
        if qqbot_app_id is not None:
            updates["qqbot_app_id"] = str(qqbot_app_id or "").strip()

        qqbot_secret = self.payload_value(payload, "qqbot_secret", "qqbotSecret")
        if qqbot_secret is not None and str(qqbot_secret).strip():
            updates["qqbot_client_secret"] = str(qqbot_secret).strip()
            updates["qqbot_bot_secret"] = str(qqbot_secret).strip()
        if bool_value(self.payload_value(payload, "clear_qqbot_secret", "clearQqbotSecret")):
            updates["qqbot_client_secret"] = ""
            updates["qqbot_bot_secret"] = ""

        qqbot_client_secret = self.payload_value(payload, "qqbot_client_secret", "qqbotClientSecret")
        if qqbot_client_secret is not None and str(qqbot_client_secret).strip():
            updates["qqbot_client_secret"] = str(qqbot_client_secret).strip()
        if bool_value(self.payload_value(payload, "clear_qqbot_client_secret", "clearQqbotClientSecret")):
            updates["qqbot_client_secret"] = ""

        qqbot_bot_secret = self.payload_value(payload, "qqbot_bot_secret", "qqbotBotSecret")
        if qqbot_bot_secret is not None and str(qqbot_bot_secret).strip():
            updates["qqbot_bot_secret"] = str(qqbot_bot_secret).strip()
        if bool_value(self.payload_value(payload, "clear_qqbot_bot_secret", "clearQqbotBotSecret")):
            updates["qqbot_bot_secret"] = ""

        qqbot_target_type = self.payload_value(payload, "qqbot_target_type", "qqbotTargetType")
        if qqbot_target_type is not None:
            normalized = str(qqbot_target_type or "subscribers").strip().lower()
            if normalized not in QQBOT_TARGET_TYPES:
                raise ApiError(400, "QQBot 通知目标类型不支持")
            updates["qqbot_target_type"] = normalized

        qqbot_target_id = self.payload_value(payload, "qqbot_target_id", "qqbotTargetId")
        if qqbot_target_id is not None:
            updates["qqbot_target_id"] = str(qqbot_target_id or "").strip()

        if any(key in updates for key in ("qqbot_app_id", "qqbot_client_secret")):
            updates["qqbot_access_token"] = ""
            updates["qqbot_access_token_expires_at"] = "0"

        next_channel = updates.get("notification_channel", current.get("notification_channel", "pushplus"))
        next_enabled = bool_value(updates.get("notification_enabled", current.get("notification_enabled")))
        next_token = updates.get("pushplus_token", current.get("pushplus_token", ""))
        if next_enabled and next_channel == "pushplus" and not next_token:
            raise ApiError(400, "启用 pushplus 前请填写 token")
        next_send_key = updates.get("serverchan_send_key", current.get("serverchan_send_key", ""))
        if next_enabled and next_channel == "serverchan" and not next_send_key:
            raise ApiError(400, "启用 Server酱 前请填写 SendKey")
        next_qqbot_app_id = updates.get("qqbot_app_id", current.get("qqbot_app_id", ""))
        next_qqbot_client_secret = updates.get("qqbot_client_secret", current.get("qqbot_client_secret", ""))
        next_qqbot_bot_secret = updates.get("qqbot_bot_secret", current.get("qqbot_bot_secret", ""))
        next_qqbot_secret = next_qqbot_client_secret or next_qqbot_bot_secret
        next_qqbot_target_type = updates.get("qqbot_target_type", current.get("qqbot_target_type", "subscribers"))
        next_qqbot_target_id = updates.get("qqbot_target_id", current.get("qqbot_target_id", ""))
        if next_enabled and next_channel == "qqbot":
            if not next_qqbot_app_id:
                raise ApiError(400, "启用 QQBot 前请填写 AppID")
            if not next_qqbot_secret:
                raise ApiError(400, "启用 QQBot 前请填写 Secret")
            if next_qqbot_target_type != "subscribers" and not next_qqbot_target_id:
                raise ApiError(400, "启用 QQBot 前请填写通知目标 ID")

        if "notification_enabled" in updates or "notification_channel" in updates:
            updates["pushplus_enabled"] = "1" if next_enabled and next_channel == "pushplus" else "0"
            updates["serverchan_enabled"] = "1" if next_enabled and next_channel == "serverchan" else "0"
            updates["qqbot_enabled"] = "1" if next_enabled and next_channel == "qqbot" else "0"

        if updates:
            self.save_app_settings(updates)
            if next_enabled:
                self.notify_open_events()
        return {"ok": True, "settings": self.notification_settings()}

    def notify_open_events(self) -> int:
        sent = 0
        for event in self.list_events(acknowledged=False):
            if self.notify_event(event):
                sent += 1
        return sent

    def send_test_active_notification(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        settings = self.notification_settings(include_secret=True)
        if payload:
            settings = self.notification_settings_with_payload(settings, payload)
        if not settings.get("notification_enabled"):
            raise ApiError(400, "请先启用通知")
        channel = settings.get("notification_channel") or "pushplus"
        event = self.test_notification_event()
        title = self.notification_title(event)
        content = self.event_markdown(event)
        if channel == "serverchan":
            if not settings.get("serverchan_send_key"):
                raise ApiError(400, "请先配置 Server酱 SendKey")
            self.send_serverchan(settings, title, content)
            return {"ok": True, "message": "Server酱测试通知已发送"}
        if channel == "qqbot":
            self.send_qqbot(settings, title, content)
            return {"ok": True, "message": "QQBot 测试通知已发送"}
        if not settings.get("pushplus_token"):
            raise ApiError(400, "请先配置 pushplus token")
        self.send_pushplus(settings, title, content)
        return {"ok": True, "message": "pushplus 测试通知已发送"}

    def notification_settings_with_payload(self, settings: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        result = dict(settings)
        enabled = self.payload_value(payload, "notification_enabled", "notificationEnabled")
        if enabled is not None:
            result["notification_enabled"] = bool_value(enabled)
            result["notificationEnabled"] = bool_value(enabled)
        channel = self.payload_value(payload, "notification_channel", "notificationChannel")
        if channel is not None:
            normalized = str(channel or "pushplus").strip().lower()
            if normalized not in NOTIFICATION_CHANNELS:
                raise ApiError(400, "通知通道不支持")
            result["notification_channel"] = normalized
            result["notificationChannel"] = normalized
        token = self.payload_value(payload, "pushplus_token", "pushplusToken")
        if token is not None and str(token).strip():
            result["pushplus_token"] = str(token).strip()
            result["pushplusToken"] = str(token).strip()
        if bool_value(self.payload_value(payload, "clear_pushplus_token", "clearPushplusToken")):
            result["pushplus_token"] = ""
            result["pushplusToken"] = ""
        send_key = self.payload_value(payload, "serverchan_send_key", "serverchanSendKey")
        if send_key is not None and str(send_key).strip():
            result["serverchan_send_key"] = str(send_key).strip()
            result["serverchanSendKey"] = str(send_key).strip()
        if bool_value(self.payload_value(payload, "clear_serverchan_send_key", "clearServerchanSendKey")):
            result["serverchan_send_key"] = ""
            result["serverchanSendKey"] = ""
        channel_value = self.payload_value(payload, "pushplus_channel", "pushplusChannel")
        if channel_value is not None:
            normalized_channel = str(channel_value or "wechat").strip().lower()
            if normalized_channel not in PUSHPLUS_CHANNELS:
                raise ApiError(400, "pushplus channel 不支持")
            result["pushplus_channel"] = normalized_channel
            result["pushplusChannel"] = normalized_channel
        template = self.payload_value(payload, "pushplus_template", "pushplusTemplate")
        if template is not None:
            normalized_template = str(template or "markdown").strip().lower()
            if normalized_template not in PUSHPLUS_TEMPLATES:
                raise ApiError(400, "pushplus template 不支持")
            result["pushplus_template"] = normalized_template
            result["pushplusTemplate"] = normalized_template
        qqbot_app_id = self.payload_value(payload, "qqbot_app_id", "qqbotAppId")
        if qqbot_app_id is not None:
            result["qqbot_app_id"] = str(qqbot_app_id or "").strip()
            result["qqbotAppId"] = str(qqbot_app_id or "").strip()
        qqbot_secret = self.payload_value(payload, "qqbot_secret", "qqbotSecret")
        if qqbot_secret is not None and str(qqbot_secret).strip():
            result["qqbot_secret"] = str(qqbot_secret).strip()
            result["qqbotSecret"] = str(qqbot_secret).strip()
            result["qqbot_client_secret"] = str(qqbot_secret).strip()
            result["qqbotClientSecret"] = str(qqbot_secret).strip()
            result["qqbot_bot_secret"] = str(qqbot_secret).strip()
            result["qqbotBotSecret"] = str(qqbot_secret).strip()
            result["qqbot_access_token"] = ""
            result["qqbotAccessToken"] = ""
            result["qqbot_access_token_expires_at"] = "0"
            result["qqbotAccessTokenExpiresAt"] = "0"
        if bool_value(self.payload_value(payload, "clear_qqbot_secret", "clearQqbotSecret")):
            result["qqbot_secret"] = ""
            result["qqbotSecret"] = ""
            result["qqbot_client_secret"] = ""
            result["qqbotClientSecret"] = ""
            result["qqbot_bot_secret"] = ""
            result["qqbotBotSecret"] = ""
            result["qqbot_access_token"] = ""
            result["qqbotAccessToken"] = ""
            result["qqbot_access_token_expires_at"] = "0"
            result["qqbotAccessTokenExpiresAt"] = "0"
        qqbot_client_secret = self.payload_value(payload, "qqbot_client_secret", "qqbotClientSecret")
        if qqbot_client_secret is not None and str(qqbot_client_secret).strip():
            result["qqbot_client_secret"] = str(qqbot_client_secret).strip()
            result["qqbotClientSecret"] = str(qqbot_client_secret).strip()
            result["qqbot_access_token"] = ""
            result["qqbotAccessToken"] = ""
            result["qqbot_access_token_expires_at"] = "0"
            result["qqbotAccessTokenExpiresAt"] = "0"
        if bool_value(self.payload_value(payload, "clear_qqbot_client_secret", "clearQqbotClientSecret")):
            result["qqbot_client_secret"] = ""
            result["qqbotClientSecret"] = ""
            result["qqbot_access_token"] = ""
            result["qqbotAccessToken"] = ""
            result["qqbot_access_token_expires_at"] = "0"
            result["qqbotAccessTokenExpiresAt"] = "0"
        qqbot_bot_secret = self.payload_value(payload, "qqbot_bot_secret", "qqbotBotSecret")
        if qqbot_bot_secret is not None and str(qqbot_bot_secret).strip():
            result["qqbot_bot_secret"] = str(qqbot_bot_secret).strip()
            result["qqbotBotSecret"] = str(qqbot_bot_secret).strip()
        if bool_value(self.payload_value(payload, "clear_qqbot_bot_secret", "clearQqbotBotSecret")):
            result["qqbot_bot_secret"] = ""
            result["qqbotBotSecret"] = ""
        qqbot_target_type = self.payload_value(payload, "qqbot_target_type", "qqbotTargetType")
        if qqbot_target_type is not None:
            normalized_target_type = str(qqbot_target_type or "subscribers").strip().lower()
            if normalized_target_type not in QQBOT_TARGET_TYPES:
                raise ApiError(400, "QQBot 通知目标类型不支持")
            result["qqbot_target_type"] = normalized_target_type
            result["qqbotTargetType"] = normalized_target_type
        qqbot_target_id = self.payload_value(payload, "qqbot_target_id", "qqbotTargetId")
        if qqbot_target_id is not None:
            result["qqbot_target_id"] = str(qqbot_target_id or "").strip()
            result["qqbotTargetId"] = str(qqbot_target_id or "").strip()
        return result

    def send_test_notification(self) -> dict[str, Any]:
        settings = self.notification_settings(include_secret=True)
        if not settings.get("pushplus_token"):
            raise ApiError(400, "请先配置 pushplus token")
        event = self.test_notification_event()
        self.send_pushplus(
            settings,
            self.notification_title(event),
            self.event_markdown(event),
        )
        return {"ok": True, "message": "pushplus 测试通知已发送"}

    def send_test_serverchan_notification(self) -> dict[str, Any]:
        settings = self.notification_settings(include_secret=True)
        if not settings.get("serverchan_send_key"):
            raise ApiError(400, "请先配置 Server酱 SendKey")
        event = self.test_notification_event()
        self.send_serverchan(
            settings,
            self.notification_title(event),
            self.event_markdown(event),
        )
        return {"ok": True, "message": "Server酱测试通知已发送"}

    def notify_event(self, event: dict[str, Any] | None, *, send_updates: bool = False) -> bool:
        if not event:
            return False
        event_type = str(event.get("type") or "")
        if event.get("notified_at") and not send_updates:
            return False
        settings = self.notification_settings(include_secret=True)
        if not settings.get("notification_enabled"):
            return False
        if event_type in {"low_balance", "balance_burnout"} and not settings.get("notify_low_balance"):
            return False
        if event_type == "rate_changed" and not settings.get("notify_rate_change"):
            return False
        if event_type == "model_probe_failed" and not settings.get("notify_model_failure"):
            return False
        if event_type in {"pool_scheduled", "pool_schedule_failed"} and not settings.get("notify_pool_schedule"):
            return False
        if event_type not in {"low_balance", "balance_burnout", "rate_changed", "model_probe_failed", "pool_scheduled", "pool_schedule_failed"}:
            return False
        brief = self.notification_brief(event)
        channel = settings.get("notification_channel") or "pushplus"
        try:
            if channel == "pushplus" and settings.get("pushplus_token"):
                self.send_pushplus(settings, brief, brief)
                self.mark_event_notified(int(event["id"]))
                return True
        except ApiError as exc:
            print(f"[pushplus] send failed: {exc.message}", flush=True)
        except Exception as exc:
            print(f"[pushplus] send failed: {exc}", flush=True)
        try:
            if channel == "serverchan" and settings.get("serverchan_send_key"):
                self.send_serverchan(settings, brief, brief)
                self.mark_event_notified(int(event["id"]))
                return True
        except ApiError as exc:
            print(f"[serverchan] send failed: {exc.message}", flush=True)
        except Exception as exc:
            print(f"[serverchan] send failed: {exc}", flush=True)
        try:
            if channel == "qqbot" and self.qqbot_settings_configured(settings):
                self.send_qqbot(settings, brief, "")
                self.mark_event_notified(int(event["id"]))
                return True
        except ApiError as exc:
            print(f"[qqbot] send failed: {exc.message}", flush=True)
        except Exception as exc:
            print(f"[qqbot] send failed: {exc}", flush=True)
        return False
