from __future__ import annotations

import re
from typing import Any

from apps.api.app.core.errors import ApiError

from .notification_constants import MONITOR_SUMMARY_EVENT_TYPES


class NotificationSummaryMixin:
    def pending_monitor_summary_events(self) -> list[dict[str, Any]]:
        return self.monitor_summary_events(include_notified=False)

    def monitor_summary_events(self, *, include_notified: bool = False) -> list[dict[str, Any]]:
        settings = self.notification_settings(include_secret=True)
        return [
            event
            for event in self.list_events(acknowledged=False)
            if self.monitor_summary_event_enabled(settings, event) and (include_notified or self.monitor_summary_event_due(event))
        ]

    def monitor_summary_event_enabled(self, settings: dict[str, Any], event: dict[str, Any]) -> bool:
        event_type = str(event.get("type") or "")
        if event_type not in MONITOR_SUMMARY_EVENT_TYPES:
            return False
        if event_type == "low_balance":
            return bool(settings.get("notify_low_balance"))
        if event_type == "rate_changed":
            return bool(settings.get("notify_rate_change"))
        if event_type == "model_probe_failed":
            return bool(settings.get("notify_model_failure"))
        if event_type == "probe_failed":
            return bool(settings.get("notify_low_balance") or settings.get("notify_rate_change"))
        return False

    def monitor_summary_event_due(self, event: dict[str, Any]) -> bool:
        notified_at = event.get("notified_at") or event.get("notifiedAt")
        if not notified_at:
            return True
        created_at = event.get("created_at") or event.get("createdAt")
        return self.notification_timestamp(created_at) > self.notification_timestamp(notified_at)

    def send_monitor_summary_notification(self, stats: dict[str, Any], events: list[dict[str, Any]], *, always: bool = False) -> bool:
        if not events and not always:
            return False
        settings = self.notification_settings(include_secret=True)
        if not settings.get("notification_enabled"):
            return False
        events = [event for event in events if self.monitor_summary_event_enabled(settings, event)]
        if not events and not always:
            return False
        rows = self.monitor_result_rows()
        title = f"📡 监控汇总：{self.monitor_attention_count(rows, events)} 项需关注"
        content = self.monitor_summary_content(stats, events, always=always, rows=rows)
        channel = settings.get("notification_channel") or "pushplus"
        try:
            if channel == "pushplus" and settings.get("pushplus_token"):
                self.send_pushplus(settings, title, content)
            elif channel == "serverchan" and settings.get("serverchan_send_key"):
                self.send_serverchan(settings, title, content)
            elif channel == "qqbot" and self.qqbot_settings_configured(settings):
                self.send_qqbot(settings, title, content)
            else:
                return False
        except ApiError as exc:
            print(f"[monitor-summary] send failed: {exc.message}", flush=True)
            return False
        except Exception as exc:
            print(f"[monitor-summary] send failed: {exc}", flush=True)
            return False
        for event in events:
            self.mark_event_notified(int(event["id"]))
        return True

    def monitor_summary_content(self, stats: dict[str, Any], events: list[dict[str, Any]], *, always: bool = False, rows: list[dict[str, Any]] | None = None) -> str:
        rows = rows if rows is not None else self.monitor_result_rows()
        if not rows:
            return "暂无可监控渠道"
        lines: list[str] = []
        groups = self.monitor_result_groups(rows)
        for index, group in enumerate(groups):
            if index:
                lines.append("")
            lines.append(f"{self.monitor_result_group_emoji(group)} {group['name']}｜余额：{group['balance']}")
            lines.extend(self.monitor_result_key_line(row) for row in group["children"])
        return "\n".join(lines)

    def monitor_result_rows(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    c.id,
                    c.name,
                    c.key_name,
                    c.source_channel_id,
                    c.is_account_parent,
                    c.balance,
                    c.unit,
                    c.threshold,
                    c.rate_multiplier,
                    c.is_monitoring,
                    c.api_key,
                    c.monitor_status,
                    parent.name AS parent_name,
                    parent.balance AS parent_balance,
                    parent.unit AS parent_unit,
                    parent.threshold AS parent_threshold
                FROM channels c
                LEFT JOIN channels parent ON parent.id = c.source_channel_id
                WHERE c.is_enabled = 1
                  AND {self.active_channel_filter}
                ORDER BY
                    CASE WHEN c.source_channel_id IS NULL THEN c.id ELSE c.source_channel_id END,
                    CASE WHEN c.source_channel_id IS NULL THEN 0 ELSE 1 END,
                    c.name COLLATE NOCASE
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def monitor_attention_count(self, rows: list[dict[str, Any]], events: list[dict[str, Any]]) -> int:
        balance_bad = len({self.monitor_result_group_key(row) for row in rows if self.monitor_result_balance_bad(row)})
        model_failed = sum(1 for row in rows if self.monitor_result_model(row) == "失败")
        event_targets = {self.notification_key_display_name(event) for event in events if str(event.get("type") or "") == "probe_failed"}
        return balance_bad + model_failed + len(event_targets)

    def monitor_result_groups(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = {}
        for row in rows:
            key = self.monitor_result_group_key(row)
            group = groups.setdefault(
                key,
                {
                    "name": self.monitor_result_group_name(row),
                    "balance": self.monitor_result_balance(row),
                    "children": [],
                },
            )
            group["children"].append(row)
            if group["balance"] == "--" and self.monitor_result_balance(row) != "--":
                group["balance"] = self.monitor_result_balance(row)
        return list(groups.values())

    def monitor_result_group_emoji(self, group: dict[str, Any]) -> str:
        children = group.get("children") or []
        if any(self.monitor_result_balance_bad(row) for row in children):
            return "🔴"
        return "🟢"

    def monitor_result_group_key(self, row: dict[str, Any]) -> str:
        parent = row.get("source_channel_id")
        if parent is not None:
            return f"parent:{parent}"
        return f"channel:{row.get('id')}"

    def monitor_result_group_name(self, row: dict[str, Any]) -> str:
        parent = str(row.get("parent_name") or "").strip()
        name = str(row.get("name") or "").strip()
        return parent or name or "未知渠道"

    def monitor_result_key_line(self, row: dict[str, Any]) -> str:
        return f"  {self.monitor_result_status_emoji(row)} {self.monitor_result_key_name(row)}｜倍率 {self.monitor_result_rate(row)}｜{self.monitor_result_status(row)}"

    def monitor_result_key_name(self, row: dict[str, Any]) -> str:
        key = str(row.get("key_name") or "").strip()
        name = str(row.get("name") or "").strip()
        parent = str(row.get("parent_name") or "").strip()
        if key:
            return key
        if parent and name.startswith(f"{parent}-"):
            return name[len(parent) + 1 :] or name
        return name or "默认"

    def monitor_result_name(self, row: dict[str, Any]) -> str:
        parent = str(row.get("parent_name") or "").strip()
        key = str(row.get("key_name") or "").strip()
        name = str(row.get("name") or "").strip()
        if parent and key:
            return f"{parent}-{key}"
        if parent and name and name != parent:
            return f"{parent}-{name}"
        return name or key or "未知渠道"

    def monitor_result_balance(self, row: dict[str, Any]) -> str:
        value, unit, _ = self.monitor_result_balance_parts(row)
        if value is None:
            return "--"
        return f"{self.monitor_number(value)} {unit or 'USD'}"

    def monitor_result_balance_parts(self, row: dict[str, Any]) -> tuple[Any, str, Any]:
        value = row.get("balance")
        unit = str(row.get("unit") or "").strip()
        threshold = row.get("threshold")
        if value is None and row.get("parent_balance") is not None:
            value = row.get("parent_balance")
            unit = str(row.get("parent_unit") or unit or "").strip()
            threshold = row.get("parent_threshold")
        return value, unit, threshold

    def monitor_result_balance_bad(self, row: dict[str, Any]) -> bool:
        value, _, threshold = self.monitor_result_balance_parts(row)
        if value is None or threshold is None:
            return False
        try:
            return float(threshold) > 0 and float(value) < float(threshold)
        except (TypeError, ValueError):
            return False

    def monitor_result_rate(self, row: dict[str, Any]) -> str:
        value = row.get("rate_multiplier")
        if value is None:
            return "--"
        return self.monitor_number(value)

    def monitor_result_model(self, row: dict[str, Any]) -> str:
        if not row.get("is_monitoring") or not row.get("api_key"):
            return "未启用"
        status = str(row.get("monitor_status") or "").strip().lower()
        if status == "healthy":
            return "成功"
        if status == "failed":
            return "失败"
        if status == "idle":
            return "待检测"
        return "待检测"

    def monitor_result_status(self, row: dict[str, Any]) -> str:
        model = self.monitor_result_model(row)
        if model == "成功":
            return "正常"
        return model

    def monitor_result_status_emoji(self, row: dict[str, Any]) -> str:
        status = self.monitor_result_status(row)
        if status == "正常":
            return "✅"
        if status == "失败":
            return "❌"
        if status == "未启用":
            return "⚪"
        return "⏳"

    def monitor_number(self, value: Any) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "--"
        if abs(number) >= 100:
            return f"{number:.2f}".rstrip("0").rstrip(".")
        if abs(number) >= 1:
            return f"{number:.2f}".rstrip("0").rstrip(".")
        return f"{number:.4f}".rstrip("0").rstrip(".")

    def monitor_scan_summary_line(self, stats: dict[str, Any]) -> str:
        balance = stats.get("balance") or {}
        rate = stats.get("rate") or {}
        model = stats.get("model") or {}
        parts = [
            self.monitor_scan_part("余额", balance),
            self.monitor_rate_scan_part(rate),
            self.monitor_scan_part("模型", model, total_key="due"),
        ]
        return "｜".join(part for part in parts if part)

    def monitor_scan_part(self, label: str, stats: dict[str, Any], *, total_key: str = "total") -> str:
        total = int(stats.get(total_key) or stats.get("total") or 0)
        ok = int(stats.get("ok") or 0)
        failed = int(stats.get("failed") or 0)
        if total <= 0:
            return f"{label} 0"
        suffix = f"，失败 {failed}" if failed else ""
        return f"{label} {ok}/{total}{suffix}"

    def monitor_rate_scan_part(self, stats: dict[str, Any]) -> str:
        total = int(stats.get("total") or 0)
        ok = int(stats.get("ok") or 0)
        failed = int(stats.get("failed") or 0)
        changed = int(stats.get("changed") or 0)
        unchanged = int(stats.get("unchanged") or 0)
        if total <= 0:
            return "倍率 0"
        suffix = f"，变动 {changed}，未变 {unchanged}"
        if failed:
            suffix = f"{suffix}，失败 {failed}"
        return f"倍率 {ok}/{total}{suffix}"

    def monitor_summary_event_line(self, event: dict[str, Any]) -> str:
        event_type = str(event.get("type") or "")
        target = self.notification_key_display_name(event)
        message = str(event.get("message") or "").strip()
        if event_type == "low_balance":
            current, threshold = self.low_balance_values(message)
            detail = current or self.clean_monitor_error(message)
            if threshold:
                return f"- 余额不足 {target}：当前 {detail}，阈值 {threshold}"
            return f"- 余额不足 {target}：{detail}"
        if event_type == "rate_changed":
            previous, current = self.rate_change_values(message)
            detail = f"{previous} -> {current}" if previous or current else self.notification_detail_text(message)
            return f"- 倍率变动 {target}：{detail}"
        if event_type == "model_probe_failed":
            return f"- 模型异常 {target}：{self.monitor_failure_reason(message)}"
        if event_type == "probe_failed":
            return f"- 探测异常 {target}：{self.monitor_failure_reason(message)}"
        return f"- {self.notification_event_label(event_type)} {target}：{self.clean_monitor_error(message)}"

    def monitor_first_failure(self, message: str) -> str:
        parts = [part.strip(" 。") for part in re.split(r"[；;\n]+", message) if part.strip(" 。")]
        if not parts:
            return "--"
        if len(parts) == 1:
            return parts[0]
        return f"{parts[0]}；另有 {len(parts) - 1} 项"

    def monitor_failure_reason(self, message: str) -> str:
        parts = [part.strip(" 。") for part in re.split(r"[；;\n]+", str(message or "")) if part.strip(" 。")]
        reasons = [self.clean_monitor_error(part) for part in parts] or ["异常"]
        unique: list[str] = []
        for reason in reasons:
            if reason not in unique:
                unique.append(reason)
        if len(unique) == 1:
            return unique[0]
        return f"{unique[0]}；另有 {len(unique) - 1} 类"

    def clean_monitor_error(self, message: str) -> str:
        text = str(message or "").strip()
        lowered = text.lower()
        if "insufficient" in lowered and "balance" in lowered:
            return "上游余额不足"
        if "token_expired" in lowered or "token has expired" in lowered or "access token" in lowered and "expired" in lowered:
            return "Token 已过期"
        if "unauthorized" in lowered or "401" in lowered:
            return "认证失败"
        if "forbidden" in lowered or "403" in lowered:
            return "权限或额度不足"
        if "timeout" in lowered or "timed out" in lowered:
            return "请求超时"
        if "rate limit" in lowered or "429" in lowered:
            return "触发限流"
        if "connection" in lowered or "network" in lowered or "网络" in text:
            return "网络异常"
        if ":" in text:
            prefix = text.split(":", 1)[0].strip()
            if prefix and len(prefix) <= 40 and not prefix.lower().startswith("http"):
                text = text.split(":", 1)[1].strip()
        text = re.sub(r"\{.*\}", "", text).strip(" ：:，,。")
        text = re.sub(r"上游 HTTP \d+", "上游异常", text).strip(" ：:，,。")
        return text[:40] or "异常"
