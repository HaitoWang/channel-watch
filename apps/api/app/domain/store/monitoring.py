from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any

from apps.api.app.core.errors import ApiError
from apps.api.app.infrastructure.integrations import query_model_probe
from apps.api.app.core.utils import utc_now


MONITOR_HISTORY_LIMIT = 60


class MonitoringMixin:
    def monitored_channels(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT c.*, parent.name AS parent_name
                FROM channels c
                LEFT JOIN channels parent ON parent.id = c.source_channel_id
                WHERE c.is_monitoring = 1
                  AND c.is_enabled = 1
                  AND c.is_account_parent = 0
                  AND c.api_key IS NOT NULL
                ORDER BY
                  CASE WHEN c.rate_multiplier IS NULL THEN 1 ELSE 0 END,
                  c.rate_multiplier ASC,
                  c.monitor_last_checked_at DESC,
                  c.name COLLATE NOCASE
                """
            ).fetchall()
        return [self.public_channel(row) for row in rows]

    def monitor_summary(self) -> dict[str, Any]:
        channels = self.monitored_channels()
        histories = self.list_history_by_channel(
            channel_ids=[int(item["id"]) for item in channels],
            kind="model",
            limit_per_channel=MONITOR_HISTORY_LIMIT,
        )
        for item in channels:
            history = histories.get(int(item["id"]), [])
            item["monitor_history"] = history
            item["monitorHistory"] = history
        healthy = sum(1 for item in channels if item.get("monitor_status") == "healthy" or item.get("monitorStatus") == "healthy")
        failed = sum(1 for item in channels if item.get("monitor_status") == "failed" or item.get("monitorStatus") == "failed")
        return {
            "summary": {
                "total": len(channels),
                "healthy": healthy,
                "failed": failed,
                "pending": max(0, len(channels) - healthy - failed),
            },
            "channels": channels,
        }

    def auto_model_probe_once(self, *, notify: bool = True) -> dict[str, int]:
        now = datetime.now(timezone.utc)
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM channels
                WHERE is_monitoring = 1
                  AND is_enabled = 1
                  AND is_account_parent = 0
                  AND api_key IS NOT NULL
                ORDER BY id
                """
            ).fetchall()
        summary = {"total": len(rows), "due": 0, "ok": 0, "failed": 0, "skipped": 0}
        for row in rows:
            if not self.model_probe_due(row, now):
                summary["skipped"] += 1
                continue
            summary["due"] += 1
            try:
                result = self.probe_models(int(row["id"]), notify=notify)
                if (result.get("result") or {}).get("ok"):
                    summary["ok"] += 1
                else:
                    summary["failed"] += 1
            except ApiError as exc:
                summary["failed"] += 1
                print(f"[model-monitor] channel {row['id']} failed: {exc.message}", flush=True)
            except Exception as exc:
                summary["failed"] += 1
                print(f"[model-monitor] channel {row['id']} failed: {exc}", flush=True)
        return summary

    def model_probe_due(self, row: sqlite3.Row, now: datetime) -> bool:
        interval = max(15, int(row["monitor_interval_seconds"] or 60))
        checked_at = row["monitor_last_checked_at"]
        if not checked_at:
            return True
        try:
            checked = datetime.fromisoformat(str(checked_at))
        except ValueError:
            return True
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=timezone.utc)
        return (now - checked).total_seconds() >= interval

    def probe_models(self, channel_id: int, *, notify: bool = True) -> dict[str, Any]:
        row = self.get_channel_row(channel_id)
        if not row:
            raise ApiError(404, "渠道不存在")
        if row["is_account_parent"] or not row["api_key"]:
            raise ApiError(400, "只有子 Key 可以启动模型监控")

        models = self.monitor_models_for_provider(row["key_provider"], row["monitor_models"])
        results: list[dict[str, Any]] = []
        failures: list[str] = []
        for model in models:
            started = time.monotonic()
            try:
                result = query_model_probe(row, model)
                latency_ms = int((time.monotonic() - started) * 1000)
                results.append({**result, "latency_ms": latency_ms, "latencyMs": latency_ms})
            except ApiError as exc:
                latency_ms = int((time.monotonic() - started) * 1000)
                failures.append(f"{model}: {exc.message}")
                results.append(
                    {
                        "ok": False,
                        "model": model,
                        "protocol": "messages" if "claude" in model.lower() else "responses",
                        "message": exc.message,
                        "latency_ms": latency_ms,
                        "latencyMs": latency_ms,
                    }
                )

        ok = not failures
        status = "healthy" if ok else "failed"
        now = utc_now()
        result_payload = {"ok": ok, "models": results, "failures": failures}
        latency_values = [item.get("latency_ms") for item in results if isinstance(item.get("latency_ms"), int)]
        latency_ms = max(latency_values) if latency_values else None
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE channels
                SET monitor_status = ?,
                    monitor_last_checked_at = ?,
                    monitor_last_error = ?,
                    monitor_latency_ms = ?,
                    monitor_result_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    now,
                    "; ".join(failures) if failures else None,
                    latency_ms,
                    json.dumps(result_payload, ensure_ascii=False),
                    now,
                    channel_id,
                ),
            )
            conn.execute(
                """
                INSERT INTO history (channel_id, kind, status, payload_json, created_at)
                VALUES (?, 'model', ?, ?, ?)
                """,
                (channel_id, "valid" if ok else "invalid", json.dumps(result_payload, ensure_ascii=False), now),
            )
        if ok:
            self.resolve_event(channel_id, "model_probe_failed")
        else:
            event_state = self.ensure_event(
                channel_id,
                "model_probe_failed",
                "critical",
                f"{row['name']} 模型监控失败",
                "；".join(failures),
            )
            if self.channel_policy_enabled(row, "disable_on_model_sync_failure"):
                self.disable_channel_scheduling(
                    channel_id,
                    row,
                    reason="model_sync_failure",
                    message=f"模型监控失败，已按渠道策略停止调度：{'；'.join(failures)}",
                    severity="critical",
                )
            if notify and event_state:
                self.notify_event(event_state["event"])
        self.maybe_pool_schedule(channel_id, notify=notify)
        return {
            "ok": ok,
            "result": result_payload,
            "channel": self.public_channel(self.get_channel_row(channel_id)),
            "monitor": self.monitor_summary(),
            "events": self.list_events(acknowledged=False),
            "overview": self.overview(),
        }
