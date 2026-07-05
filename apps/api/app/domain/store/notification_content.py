from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from apps.api.app.core.utils import utc_now


class NotificationContentMixin:
    def event_markdown(self, event: dict[str, Any]) -> str:
        event_type = str(event.get("type") or "")
        message = str(event.get("message") or "").strip()
        lines = self.notification_common_lines(event)
        if event_type == "low_balance":
            current, threshold = self.low_balance_values(message)
            if current:
                lines.append(f"当前余额：{current}")
            if threshold:
                lines.append(f"告警阈值：{threshold}")
            if not current and not threshold:
                lines.append(f"详情：{self.notification_detail_text(message)}")
            lines.append("建议：请及时充值，或先切换到备用渠道。")
            return "\n".join(lines)
        if event_type == "rate_changed":
            previous, current = self.rate_change_values(message)
            if previous or current:
                lines.append(f"倍率变化：{previous or '--'} -> {current or '--'}")
            else:
                lines.append(f"详情：{self.notification_detail_text(message)}")
            lines.append("建议：确认分组价格变化，必要时调整路由策略。")
            return "\n".join(lines)
        if event_type == "model_probe_failed":
            lines.extend(self.model_failure_lines(message))
            lines.append("建议：检查模型权限、密钥状态和上游接口可用性。")
            return "\n".join(lines)
        lines.append(f"详情：{self.notification_detail_text(message) or self.notification_title(event)}")
        return "\n".join(lines)

    def notification_common_lines(self, event: dict[str, Any]) -> list[str]:
        lines = [
            f"事件：{self.notification_event_label(event.get('type'))}",
            f"级别：{self.notification_severity_label(event.get('severity'))}",
            f"对象：{self.notification_key_display_name(event)}",
        ]
        platform = self.notification_platform_label(event.get("platform"))
        if platform:
            lines.append(f"平台：{platform}")
        created_at = self.notification_time_text(event.get("created_at") or event.get("createdAt"))
        if created_at:
            lines.append(f"时间：{created_at}")
        return lines

    def notification_short(self, content: str) -> str:
        text = " ".join(str(content or "").split())
        return text[:64] if len(text) > 64 else text

    def low_balance_remaining_text(self, message: str) -> str:
        if "当前余额" not in message:
            return ""
        value = message.split("当前余额", 1)[1].split("，", 1)[0]
        return value.strip(" 。")

    def low_balance_values(self, message: str) -> tuple[str, str]:
        match = re.search(r"当前余额\s*([+-]?\d+(?:\.\d+)?)\s*([^，,。\s]+)?[，,\s]+阈值\s*([+-]?\d+(?:\.\d+)?)\s*([^，,。\s]+)?", message)
        if not match:
            return "", ""
        current_value, current_unit, threshold_value, threshold_unit = match.groups()
        unit = current_unit or threshold_unit or ""
        return f"{current_value} {unit}".strip(), f"{threshold_value} {threshold_unit or unit}".strip()

    def notification_detail_text(self, message: str) -> str:
        return str(message or "").strip(" 。") or "--"

    def rate_change_text(self, message: str) -> str:
        if "倍率从" in message and "变为" in message:
            previous = message.split("倍率从", 1)[1].split("变为", 1)[0].strip()
            current = message.split("变为", 1)[1].strip(" 。")
            return f"{previous} -> {current}"
        return message.strip(" 。")

    def rate_change_values(self, message: str) -> tuple[str, str]:
        match = re.search(r"倍率从\s*([^，,。\s]+)\s*变为\s*([^，,。\s]+)", message)
        if not match:
            return "", ""
        return match.group(1).strip(), match.group(2).strip()

    def model_failure_lines(self, message: str) -> list[str]:
        parts = [part.strip(" 。") for part in re.split(r"[；;\n]+", message) if part.strip(" 。")]
        if not parts:
            return ["失败原因：--"]
        if len(parts) == 1:
            return [f"失败原因：{parts[0]}"]
        lines = ["失败原因："]
        lines.extend(f"- {part}" for part in parts[:5])
        if len(parts) > 5:
            lines.append(f"- 另有 {len(parts) - 5} 条失败")
        return lines

    def notification_title(self, event: dict[str, Any]) -> str:
        event_type = str(event.get("type") or "")
        if event_type == "low_balance":
            return "余额监控：余额不足"
        if event_type == "rate_changed":
            return "倍率监控：发生变化"
        if event_type == "model_probe_failed":
            return "模型监控：调用失败"
        return str(event.get("title") or "告警")

    def notification_channel_name(self, event: dict[str, Any]) -> str:
        return str(event.get("channel_name") or event.get("channelName") or "未知渠道")

    def notification_key_display_name(self, event: dict[str, Any]) -> str:
        parent = str(event.get("parent_name") or event.get("parentName") or "").strip()
        key = str(event.get("key_name") or event.get("keyName") or "").strip()
        channel = self.notification_channel_name(event)
        if parent and key:
            return f"{parent}-{key}"
        if parent and channel and channel != parent:
            return f"{parent}-{channel}"
        if key and channel and key != channel:
            return f"{channel}-{key}"
        return channel or key or "未知渠道"

    def rate_current_text(self, message: str) -> str:
        if "变为" in message:
            return message.split("变为", 1)[1].strip(" 。")
        if "倍率从" in message:
            return message.split("倍率从", 1)[1].strip(" 。")
        return message.strip(" 。")

    def notification_platform_label(self, value: Any) -> str:
        platform = str(value or "").strip()
        if platform == "newApi":
            return "New API"
        if platform == "sub2Api":
            return "Sub2API"
        return platform

    def notification_severity_label(self, value: Any) -> str:
        severity = str(value or "").strip().lower()
        if severity == "critical":
            return "严重"
        if severity == "warning":
            return "警告"
        if severity == "info":
            return "提示"
        return severity or "告警"

    def notification_time_text(self, value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        try:
            parsed = self.notification_timestamp(raw)
            if parsed == datetime.min.replace(tzinfo=timezone.utc):
                return raw
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            shanghai = parsed.astimezone(timezone(timedelta(hours=8)))
            return f"{shanghai:%Y-%m-%d %H:%M:%S} 北京时间"
        except ValueError:
            return raw

    def notification_timestamp(self, value: Any) -> datetime:
        raw = str(value or "").strip()
        if not raw:
            return datetime.min.replace(tzinfo=timezone.utc)
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return datetime.min.replace(tzinfo=timezone.utc)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    def test_notification_event(self) -> dict[str, Any]:
        return {
            "type": "low_balance",
            "channel_name": "测试渠道",
            "platform": "newApi",
            "severity": "warning",
            "message": "当前余额 1 USD，阈值 10 USD。",
            "created_at": utc_now(),
        }

    def notification_event_label(self, value: Any) -> str:
        if value == "low_balance":
            return "余额低于阈值"
        if value == "rate_changed":
            return "倍率变化"
        if value == "model_probe_failed":
            return "模型监控失败"
        if value == "probe_failed":
            return "探测失败"
        return str(value or "告警")

    def save_app_settings(self, values: dict[str, str]) -> None:
        now = utc_now()
        with self.connect() as conn:
            for key, value in values.items():
                conn.execute(
                    """
                    INSERT INTO app_settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                    """,
                    (key, value, now),
                )

    def payload_value(self, payload: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in payload:
                return payload[key]
        return None
