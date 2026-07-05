from __future__ import annotations

import json
import re
from typing import Any

from apps.api.app.core.errors import ApiError
from apps.api.app.core.utils import utc_now

from .notification_constants import QQBOT_TARGET_ENDPOINTS, QQBOT_TARGET_LABELS, sign_validation, verify_callback


class NotificationQqbotMixin:
    def handle_qqbot_webhook(self, headers: dict[str, str], body: bytes) -> dict[str, Any]:
        settings = self.notification_settings(include_secret=True)
        bot_secret = str(settings.get("qqbot_secret") or settings.get("qqbotSecret") or settings.get("qqbot_bot_secret") or settings.get("qqbotBotSecret") or "").strip()
        if not bot_secret:
            raise ApiError(400, "QQBot Secret 未配置")
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except json.JSONDecodeError as exc:
            raise ApiError(400, "QQBot 回调 JSON 格式错误") from exc
        if not isinstance(payload, dict):
            raise ApiError(400, "QQBot 回调体必须是 JSON 对象")

        op = self.qqbot_int(payload.get("op"), default=-1)
        if op == 13:
            data = payload.get("d") if isinstance(payload.get("d"), dict) else {}
            plain_token = str(data.get("plain_token") or "")
            event_ts = str(data.get("event_ts") or "")
            if not plain_token or not event_ts:
                raise ApiError(400, "QQBot 回调验证参数缺失")
            return {"plain_token": plain_token, "signature": sign_validation(bot_secret, event_ts, plain_token)}

        signature = self.qqbot_header(headers, "X-Signature-Ed25519")
        timestamp = self.qqbot_header(headers, "X-Signature-Timestamp")
        if not verify_callback(bot_secret, timestamp, body, signature):
            raise ApiError(401, "QQBot 回调签名校验失败")

        if op == 0:
            self.record_qqbot_event(payload)
        return {"op": 12}

    def qqbot_header(self, headers: dict[str, str], name: str) -> str:
        target = name.lower()
        for key, value in headers.items():
            if key.lower() == target:
                return value
        return ""

    def update_qqbot_gateway_status(
        self,
        status: str,
        *,
        error: str = "",
        connected: bool = False,
        session_id: str | None = None,
        seq: int | str | None = None,
    ) -> None:
        updates = {
            "qqbot_gateway_status": str(status or "stopped"),
            "qqbot_gateway_last_error": str(error or "")[:500],
        }
        if connected:
            updates["qqbot_gateway_last_connected_at"] = utc_now()
        if session_id is not None:
            updates["qqbot_gateway_session_id"] = str(session_id or "")
        if seq is not None:
            updates["qqbot_gateway_seq"] = str(seq or "")
        self.save_app_settings(updates)

    def record_qqbot_gateway_sequence(self, seq: int | str | None) -> None:
        if seq is None or seq == "":
            return
        self.save_app_settings({"qqbot_gateway_seq": str(seq)})

    def record_qqbot_event(self, payload: dict[str, Any]) -> None:
        event_type = str(payload.get("t") or "")
        data = payload.get("d") if isinstance(payload.get("d"), dict) else {}
        target_type, target_id = self.extract_qqbot_target(event_type, data)
        updates = {"qqbot_last_event_type": event_type, "qqbot_last_event_at": utc_now()}
        if target_type and target_id:
            updates["qqbot_last_target_type"] = target_type
            updates["qqbot_last_target_id"] = target_id
            created = self.upsert_qqbot_subscriber(target_type, target_id, event_type)
            current = self.notification_settings(include_secret=True)
            if str(current.get("qqbot_target_type") or "subscribers").strip().lower() != "subscribers" and not str(current.get("qqbot_target_id") or "").strip():
                updates["qqbot_target_type"] = target_type
                updates["qqbot_target_id"] = target_id
            if self.qqbot_is_test_command(data):
                self.reply_qqbot_test(current, target_type, target_id)
            elif created or self.qqbot_should_reply_subscriber_id(data):
                self.reply_qqbot_subscriber_id(current, target_type, target_id)
        self.save_app_settings(updates)

    def list_qqbot_subscribers(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        sql = """
            SELECT target_type, target_id, source_event, created_at, last_seen_at
            FROM qqbot_subscribers
            WHERE is_enabled = 1
            ORDER BY last_seen_at DESC
        """
        params: tuple[Any, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (max(0, int(limit)),)
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def upsert_qqbot_subscriber(self, target_type: str, target_id: str, event_type: str) -> bool:
        if target_type not in QQBOT_TARGET_ENDPOINTS or not target_id:
            return False
        now = utc_now()
        with self.connect() as conn:
            existing = conn.execute(
                """
                SELECT 1
                FROM qqbot_subscribers
                WHERE target_type = ? AND target_id = ?
                """,
                (target_type, target_id),
            ).fetchone()
            conn.execute(
                """
                INSERT INTO qqbot_subscribers (target_type, target_id, source_event, created_at, last_seen_at, is_enabled)
                VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(target_type, target_id)
                DO UPDATE SET
                    source_event = excluded.source_event,
                    last_seen_at = excluded.last_seen_at,
                    is_enabled = 1
                """,
                (target_type, target_id, event_type, now, now),
            )
        return existing is None

    def qqbot_should_reply_subscriber_id(self, data: dict[str, Any]) -> bool:
        content = self.qqbot_message_content(data).lower()
        return "openid" in content or "open id" in content or "订阅" in content

    def qqbot_is_test_command(self, data: dict[str, Any]) -> bool:
        return self.qqbot_command_text(data) == "测试"

    def qqbot_command_text(self, data: dict[str, Any]) -> str:
        content = self.qqbot_message_content(data).replace("\u00a0", " ").strip()
        content = re.sub(r"<@!?[0-9A-Za-z_-]+>", "", content).strip()
        content = content.lstrip("/!！#＃").strip()
        return " ".join(content.split()).lower()

    def qqbot_message_content(self, data: dict[str, Any]) -> str:
        return str(data.get("content") or data.get("text") or data.get("message") or "").strip()

    def reply_qqbot_test(self, settings: dict[str, Any], target_type: str, target_id: str) -> None:
        if not self.qqbot_settings_configured({**settings, "qqbot_target_type": target_type, "qqbot_target_id": target_id}):
            return
        try:
            self.send_qqbot_text(settings, target_type, target_id, "测试成功，QQBot 已收到你的消息。")
        except ApiError as exc:
            print(f"[qqbot] test reply failed: {exc.message}", flush=True)
        except Exception as exc:
            print(f"[qqbot] test reply failed: {exc}", flush=True)

    def reply_qqbot_subscriber_id(self, settings: dict[str, Any], target_type: str, target_id: str) -> None:
        if not self.qqbot_settings_configured({**settings, "qqbot_target_type": target_type, "qqbot_target_id": target_id}):
            return
        id_label = {
            "group": "group_openid",
            "user": "openid",
            "channel": "channel_id",
            "guild_dm": "guild_id",
        }.get(target_type, "target_id")
        label = QQBOT_TARGET_LABELS.get(target_type, "QQBot")
        content = f"已记录 {label} 通知订阅\n{id_label}: {target_id}"
        try:
            self.send_qqbot_text(settings, target_type, target_id, content)
        except ApiError as exc:
            print(f"[qqbot] reply failed: {exc.message}", flush=True)
        except Exception as exc:
            print(f"[qqbot] reply failed: {exc}", flush=True)

    def extract_qqbot_target(self, event_type: str, data: dict[str, Any]) -> tuple[str, str]:
        author = data.get("author") if isinstance(data.get("author"), dict) else {}
        member = data.get("member") if isinstance(data.get("member"), dict) else {}
        user = data.get("user") if isinstance(data.get("user"), dict) else {}
        group_id = str(data.get("group_openid") or data.get("groupOpenid") or data.get("group_id") or data.get("groupId") or "").strip()
        openid = str(
            data.get("openid")
            or data.get("open_id")
            or data.get("user_openid")
            or data.get("userOpenid")
            or author.get("user_openid")
            or author.get("userOpenid")
            or author.get("openid")
            or member.get("user_openid")
            or member.get("userOpenid")
            or member.get("openid")
            or user.get("user_openid")
            or user.get("userOpenid")
            or user.get("openid")
            or ""
        ).strip()
        channel_id = str(data.get("channel_id") or data.get("channelId") or "").strip()
        guild_id = str(data.get("guild_id") or data.get("guildId") or "").strip()
        if group_id and event_type.startswith("GROUP_"):
            return "group", group_id
        if openid and event_type.startswith(("C2C_", "FRIEND_")):
            return "user", openid
        if channel_id:
            return "channel", channel_id
        if guild_id and event_type.startswith("DIRECT_"):
            return "guild_dm", guild_id
        if group_id:
            return "group", group_id
        if openid:
            return "user", openid
        return "", ""
