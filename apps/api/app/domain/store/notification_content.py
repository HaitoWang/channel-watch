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

    def _fmt_num(self, value: Any, digits: int = 2) -> str:
        """数字格式化：保留至多 digits 位小数，去掉无意义尾随 0。"""
        try:
            f = float(value)
        except (TypeError, ValueError):
            return str(value or "")
        s = f"{f:.{digits}f}".rstrip("0").rstrip(".")
        return s or "0"

    def notification_brief(self, event: dict[str, Any]) -> str:
        """即时推送文案（QQBot 等）：统一的多行卡片格式，带 emoji、数值规整、含处置建议。"""
        name = self.notification_key_display_name(event)
        event_type = str(event.get("type") or "")
        message = str(event.get("message") or "")

        if event_type == "low_balance":
            m = re.search(r"当前余额\s*([-\d.]+)\s*(\S+?)[，,]", message)
            amount = self._fmt_num(m.group(1)) if m else ""
            unit = m.group(2) if m else "USD"
            try:
                num = float(m.group(1)) if m else 0.0
            except (TypeError, ValueError):
                num = 0.0
            if not m:
                bal_line = "余额不足"
            elif num <= 0:
                bal_line = f"已欠费 {self._fmt_num(abs(num))} {unit}"
            else:
                bal_line = f"剩余 {amount} {unit}"
            return "\n".join([
                "🔴 余额不足",
                f"🏷 {name}",
                f"💰 {bal_line}",
                "💡 请尽快充值",
            ])

        if event_type == "balance_burnout":
            hm = re.search(r"预计\s*([\d.]+)\s*小时", message)
            cm = re.search(r"当前\s*([-\d.]+)\s*(\S+?)[，,]", message)
            hours = self._fmt_num(hm.group(1), 1) if hm else "很快"
            lines = ["⏳ 余额将耗尽", f"🏷 {name}"]
            if cm:
                lines.append(f"💰 剩余 {self._fmt_num(cm.group(1))} {cm.group(2)}")
            lines.append(f"⏱ 预计 {hours} 小时后耗尽")
            lines.append("💡 建议提前充值")
            return "\n".join(lines)

        if event_type == "rate_changed":
            previous, current = self.rate_change_values(message)
            trend = ""
            try:
                trend = " ↑" if float(current) > float(previous) else " ↓"
            except (TypeError, ValueError):
                trend = ""
            return "\n".join([
                "📈 倍率变动",
                f"🏷 {name}",
                f"⚙️ {self._fmt_num(previous, 4)} → {self._fmt_num(current, 4)}{trend}",
                "💡 注意切换，避免损失",
            ])

        if event_type == "model_probe_failed":
            models = self.model_failure_models(message)
            return "\n".join([
                "🚨 模型异常",
                f"🏷 {name}",
                f"🤖 {models}",
                "💡 请检查上游可用性",
            ])

        if event_type == "pool_scheduled":
            # message 形如「已启用号池账号 [9]。原因：...」
            enabled = "启用" in message.split("原因", 1)[0]
            emoji = "🟢" if enabled else "🔴"
            action = "已启用调度" if enabled else "已停止调度"
            reason = message.split("原因：", 1)[1].strip("。") if "原因：" in message else ""
            lines = [f"{emoji} 号池{action}", f"🏷 {name}"]
            if reason:
                lines.append(f"📋 {reason}")
            return "\n".join(lines)

        if event_type == "pool_schedule_failed":
            detail = message.split("：", 1)[1] if "：" in message else message
            return "\n".join([
                "⚠️ 号池调度下发失败",
                f"🏷 {name}",
                f"📋 {detail.strip()[:80]}",
                "💡 请检查号池连接",
            ])

        return f"⚠️ {name}：{self.notification_event_label(event_type)}"

    def model_failure_models(self, message: str) -> str:
        """从模型失败详情里提取出错的模型名，用 / 连接（如 gpt-5.5/claude）。"""
        parts = [part.strip() for part in re.split(r"[；;\n]+", message) if part.strip()]
        models: list[str] = []
        for part in parts:
            name = re.split(r"[:：]", part, 1)[0].strip()
            if name and name not in models:
                models.append(name)
        return "/".join(models[:3]) if models else "模型"

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
