from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import sqlite3
from typing import Any

from apps.api.app.core.errors import ApiError
from apps.api.app.infrastructure.integrations import (
    demo_balance_result,
    demo_group_result,
    find_group,
    public_key_items,
    query_real_balance,
    query_real_group_catalog,
    query_sub2api_keys,
    refresh_sub2api_session,
    login_sub2api_credentials,
)
from apps.api.app.core.utils import optional_float, utc_now


MAX_SCAN_WORKERS = 8


class ProbeServiceMixin:
    def auto_balance_rate_scan_once(self, *, include_balance: bool = True, include_rate: bool = True, notify: bool = True) -> dict[str, dict[str, int]]:
        print("[balance-rate-scan] scan started", flush=True)
        balance = self.auto_probe_once(notify=notify) if include_balance else {"total": 0, "ok": 0, "failed": 0}
        rate = self.auto_group_probe_once(notify=notify) if include_rate else {"total": 0, "ok": 0, "failed": 0}
        print(
            "[balance-rate-scan] "
            f"balance {balance['ok']}/{balance['total']} ok, {balance['failed']} failed; "
            f"rate {rate['ok']}/{rate['total']} ok, {rate['failed']} failed",
            flush=True,
        )
        return {"balance": balance, "rate": rate}

    def unified_monitor_scan_once(self, *, include_balance: bool = True, include_rate: bool = True, include_model: bool = True) -> dict[str, Any]:
        print("[unified-monitor] scan started", flush=True)
        # notify=True：仅在余额低于阈值 / 模型出错 / 倍率变动时各自发通知（去重靠 notified_at），
        # 不再无条件推送监控汇总。
        balance = self.auto_probe_once(notify=True) if include_balance else {"total": 0, "ok": 0, "failed": 0}
        rate = self.auto_group_probe_once(notify=True) if include_rate else {"total": 0, "ok": 0, "failed": 0}
        model = self.auto_model_probe_once(notify=True) if include_model else {"total": 0, "due": 0, "ok": 0, "failed": 0, "skipped": 0}
        stats = {"balance": balance, "rate": rate, "model": model}
        print(
            "[unified-monitor] "
            f"balance {balance['ok']}/{balance['total']} ok, {balance['failed']} failed; "
            f"rate {rate['ok']}/{rate['total']} ok, {rate['failed']} failed; "
            f"model {model['ok']}/{model.get('due', model['total'])} ok, {model['failed']} failed",
            flush=True,
        )
        return {"stats": stats}

    def auto_probe_once(self, *, notify: bool = True) -> dict[str, int]:
        channel_ids = self.enabled_channel_ids()
        return self._run_probe_batch("auto-probe", channel_ids, lambda channel_id: self.probe_balance(channel_id, notify=notify))

    def auto_group_probe_once(self, *, notify: bool = True) -> dict[str, int]:
        channel_ids = self.rate_probe_channel_ids()
        return self._run_probe_batch("rate-probe", channel_ids, lambda channel_id: self.probe_groups(channel_id, notify=notify))

    def _run_probe_batch(
        self,
        name: str,
        channel_ids: list[int],
        probe: Callable[[int], dict[str, Any]],
    ) -> dict[str, int]:
        summary = {"total": len(channel_ids), "ok": 0, "failed": 0, "changed": 0, "unchanged": 0}
        if not channel_ids:
            return summary
        max_workers = max(1, min(MAX_SCAN_WORKERS, len(channel_ids)))
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix=f"channel-radar-{name}") as executor:
            futures = {executor.submit(probe, channel_id): channel_id for channel_id in channel_ids}
            for future in as_completed(futures):
                channel_id = futures[future]
                try:
                    result = future.result()
                    summary["ok"] += 1
                    result_payload = result.get("result") if isinstance(result, dict) else None
                    if isinstance(result_payload, dict) and "changed" in result_payload:
                        if result_payload.get("changed"):
                            summary["changed"] += 1
                        else:
                            summary["unchanged"] += 1
                except ApiError as exc:
                    summary["failed"] += 1
                    print(f"[{name}] channel {channel_id} failed: {exc.message}", flush=True)
                except Exception as exc:
                    summary["failed"] += 1
                    print(f"[{name}] channel {channel_id} failed: {exc}", flush=True)
        return summary

    def rate_probe_channel_ids(self) -> list[int]:
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT c.id
                FROM channels c
                WHERE c.is_enabled = 1
                  AND {self.active_channel_filter}
                ORDER BY c.id
                """
            ).fetchall()
        return [int(row["id"]) for row in rows]

    def probe_balance(self, channel_id: int, *, notify: bool = True) -> dict[str, Any]:
        row = self.get_channel_row(channel_id)
        if not row:
            raise ApiError(404, "渠道不存在")
        row = self.balance_probe_row(row)
        channel_id = int(row["id"])
        try:
            row, result = self.sub2api_probe_call(
                channel_id,
                row,
                lambda r: demo_balance_result(r) if r["is_demo"] else query_real_balance(r),
            )
        except ApiError as exc:
            self._record_probe_failure(channel_id, row, exc.message)
            raise
        except Exception as exc:
            message = f"探测失败: {exc}"
            self._record_probe_failure(channel_id, row, message)
            raise ApiError(502, message) from exc
        self._apply_balance_result(channel_id, row, result, notify=notify)
        return {
            "ok": True,
            "result": result,
            "channel": self.public_channel(self.get_channel_row(channel_id)),
            "overview": self.overview(),
            "events": self.list_events(acknowledged=False),
        }

    def should_retry_sub2api_session(self, row: sqlite3.Row, exc: ApiError) -> bool:
        if row["is_demo"] or row["platform"] != "sub2Api":
            return False
        token_expired = "TOKEN_EXPIRED" in str(exc.message or "").upper()
        if exc.status not in {401, 403} and not token_expired:
            return False
        return bool(row["refresh_token"] or (row["email"] and row["password"]))

    def balance_probe_row(self, row: sqlite3.Row) -> sqlite3.Row:
        parent_id = row["source_channel_id"]
        if parent_id is None:
            return row
        parent = self.get_channel_row(int(parent_id))
        return parent or row

    def probe_groups(self, channel_id: int, *, notify: bool = True) -> dict[str, Any]:
        row = self.get_channel_row(channel_id)
        if not row:
            raise ApiError(404, "渠道不存在")
        try:
            row, groups = self.sub2api_probe_call(channel_id, row, lambda r: self.load_group_catalog(r))
            result = find_group(groups, row["group_id"]) or (groups[0] if groups else None)
            if not result:
                raise ApiError(502, "未获取到可用分组")
            self.store_channel_groups(channel_id, groups)
        except ApiError as exc:
            self._record_probe_failure(channel_id, row, exc.message, kind="group")
            raise
        except Exception as exc:
            message = f"倍率探测失败: {exc}"
            self._record_probe_failure(channel_id, row, message, kind="group")
            raise ApiError(502, message) from exc
        previous_rate = optional_float(row["rate_multiplier"])
        current_rate = optional_float(result.get("rate_multiplier"))
        changed = previous_rate is not None and current_rate is not None and previous_rate != current_rate
        balance = optional_float(row["balance"])
        threshold = optional_float(row["threshold"]) or 0
        next_status = row["status"]
        if balance is not None:
            next_status = "warning" if threshold > 0 and balance < threshold else "healthy"
        elif row["status"] == "offline":
            next_status = "never"
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE channels
                SET group_id = COALESCE(?, group_id),
                    group_name = COALESCE(?, group_name),
                    rate_multiplier = COALESCE(?, rate_multiplier),
                    status = ?,
                    last_error = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (result.get("group_id"), result.get("group_name"), current_rate, next_status, now, channel_id),
            )
            conn.execute(
                """
                INSERT INTO history (channel_id, kind, status, rate_multiplier, payload_json, created_at)
                VALUES (?, 'group', 'valid', ?, ?, ?)
                """,
                (channel_id, current_rate, json.dumps(result, ensure_ascii=False), now),
            )
        self.resolve_event(channel_id, "probe_failed")
        if changed:
            event_state = self.ensure_event(
                channel_id,
                "rate_changed",
                "warning",
                f"{row['name']} 分组倍率变化",
                f"倍率从 {previous_rate:g} 变为 {current_rate:g}。",
            )
            if self.channel_policy_enabled(row, "disable_on_rate_multiplier_change"):
                self.disable_channel_scheduling(
                    channel_id,
                    row,
                    reason="rate_multiplier_change",
                    message=f"检测到倍率从 {previous_rate:g} 变为 {current_rate:g}，已按渠道策略停止调度。",
                    severity="warning",
                )
            if notify:
                self.notify_event(event_state["event"] if event_state else None, send_updates=True)
        self.maybe_pool_schedule(channel_id, notify=notify)
        return {
            "ok": True,
            "result": {**result, "changed": changed, "previous_rate": previous_rate},
            "channel": self.public_channel(self.get_channel_row(channel_id)),
            "overview": self.overview(),
            "events": self.list_events(acknowledged=False),
        }

    def load_group_catalog(self, row: sqlite3.Row) -> list[dict[str, Any]]:
        groups = [demo_group_result(row)] if row["is_demo"] else query_real_group_catalog(row)
        if not groups:
            raise ApiError(502, "未获取到可用分组")
        return groups

    def sync_user_keys(self, channel_id: int, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        row = self.get_channel_row(channel_id)
        if not row:
            raise ApiError(404, "渠道不存在")
        row = self.ensure_sub2api_session(
            channel_id,
            row,
            str((payload or {}).get("turnstile_token") or (payload or {}).get("turnstileToken") or "").strip() or None,
        )

        groups = self.load_group_catalog(row)
        selected = find_group(groups, row["group_id"]) or groups[0]
        self.store_channel_groups(channel_id, groups)
        current_rate = optional_float(selected.get("rate_multiplier") if selected else None)
        balance = optional_float(row["balance"])
        threshold = optional_float(row["threshold"]) or 0
        next_status = row["status"]
        if balance is not None:
            next_status = "warning" if threshold > 0 and balance < threshold else "healthy"
        elif row["status"] == "offline":
            next_status = "never"
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE channels
                SET group_id = COALESCE(?, group_id),
                    group_name = COALESCE(?, group_name),
                    rate_multiplier = COALESCE(?, rate_multiplier),
                    status = ?,
                    last_error = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    selected.get("group_id"),
                    selected.get("group_name"),
                    current_rate,
                    next_status,
                    now,
                    channel_id,
                ),
            )
            conn.execute(
                """
                INSERT INTO history (channel_id, kind, status, rate_multiplier, payload_json, created_at)
                VALUES (?, 'group', 'valid', ?, ?, ?)
                """,
                (
                    channel_id,
                    current_rate,
                    json.dumps({"selected": selected, "groups": groups}, ensure_ascii=False),
                    now,
                ),
            )

        keys: list[dict[str, Any]] = []
        imported_ids: list[int] = []
        if not row["is_demo"] and row["platform"] == "sub2Api":
            keys = query_sub2api_keys(row)
            imported_ids = self.upsert_synced_keys(row, keys, groups)
            for imported_id in imported_ids:
                self.store_channel_groups(imported_id, groups)

        self.resolve_event(channel_id, "probe_failed")
        channel_row = self.get_channel_row(channel_id)
        if not channel_row and imported_ids:
            channel_row = self.get_channel_row(imported_ids[0])
        channels = self.list_channels()
        return {
            "ok": True,
            "imported": len(imported_ids),
            "keys": public_key_items(keys),
            "groups": groups,
            "channel": self.public_channel(channel_row) if channel_row else None,
            "channels": channels,
            "overview": self.overview(),
            "events": self.list_events(acknowledged=False),
        }

    def _sub2api_global_turnstile(self) -> str | None:
        """读取全局配置的 turnstile 校验 token（用于自动重登时的 CF 兜底）。"""
        try:
            token = (self.sub2api_settings(include_secret=True).get("sub2api_turnstile_token") or "").strip()
        except Exception:  # noqa: BLE001 —— 配置读取异常不应影响探测
            return None
        return token or None

    def ensure_sub2api_session(
        self,
        channel_id: int,
        row: sqlite3.Row,
        turnstile_token: str | None = None,
        force_refresh: bool = False,
    ) -> sqlite3.Row:
        if row["is_demo"] or row["platform"] != "sub2Api":
            return row
        if row["access_token"] and not force_refresh:
            return row
        auth: dict[str, str | None] | None = None
        if row["refresh_token"]:
            try:
                auth = refresh_sub2api_session(row["base_url"], row["refresh_token"])
            except ApiError:
                auth = None
        if not auth and row["email"] and row["password"]:
            # 密码登录：优先用调用方传入的 turnstile，否则回落全局配置（CF 兜底）
            token = turnstile_token or self._sub2api_global_turnstile()
            auth = login_sub2api_credentials(row["base_url"], row["email"], row["password"], token)
        if not auth or not auth.get("access_token"):
            return row
        return self._persist_sub2api_tokens(channel_id, row, auth)

    def _persist_sub2api_tokens(self, channel_id: int, row: sqlite3.Row, auth: dict[str, str | None]) -> sqlite3.Row:
        """把刷新/登录拿到的 token 写回整个账号族（父账号 + 全部子 Key），
        避免多个 Key 各自重复刷新导致（一次性轮换的）refresh_token 互相失效。"""
        now = utc_now()
        family_root = row["source_channel_id"] or channel_id
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE channels
                SET access_token = COALESCE(?, access_token),
                    refresh_token = COALESCE(?, refresh_token),
                    user_id = COALESCE(?, user_id),
                    updated_at = ?
                WHERE id = ? OR id = ? OR source_channel_id = ?
                """,
                (auth.get("access_token"), auth.get("refresh_token"), auth.get("user_id"), now, channel_id, family_root, family_root),
            )
        return self.get_channel_row(channel_id) or row

    def relogin_sub2api(self, channel_id: int, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """手动重新登录：用已存（或本次传入）的 email/password + 一次性 turnstile(CF) 重登，
        拿到新的 access/refresh token 并写回账号族。用于 refresh_token 也失效、
        且上游登录带 Cloudflare 校验的账号。"""
        row = self.get_channel_row(channel_id)
        if not row:
            raise ApiError(404, "渠道不存在")
        if row["platform"] != "sub2Api":
            raise ApiError(400, "仅 sub2Api 渠道支持重新登录")
        p = payload or {}
        email = str(p.get("email") or row["email"] or "").strip()
        password = str(p.get("password") or row["password"] or "").strip()
        turnstile = str(p.get("turnstile_token") or p.get("turnstileToken") or "").strip() or None
        if not (email and password):
            raise ApiError(400, "该渠道未保存账号密码，无法自动重新登录；请直接更新 accessToken / refreshToken")
        auth = login_sub2api_credentials(row["base_url"], email, password, turnstile)
        if not auth.get("access_token"):
            raise ApiError(502, "重新登录未返回 access_token")
        # 若本次传入了新的 email/password，一并持久化（父账号级）
        if p.get("email") or p.get("password"):
            with self.connect() as conn:
                conn.execute(
                    "UPDATE channels SET email = COALESCE(?, email), password = COALESCE(?, password), updated_at = ? WHERE id = ?",
                    (email or None, password or None, utc_now(), int(row["source_channel_id"] or channel_id)),
                )
        row = self._persist_sub2api_tokens(channel_id, row, auth)
        return {"ok": True, "channel": self.public_channel(row)}

    def sub2api_probe_call(self, channel_id: int, row: sqlite3.Row, call, *, turnstile_token: str | None = None):
        """确保 sub2api 会话有效并执行 call(row)；遇 401/403（含 TOKEN_EXPIRED）
        自动重登刷新后重试一次。返回 (最新 row, 结果)。"""
        row = self.ensure_sub2api_session(channel_id, row, turnstile_token)
        try:
            return row, call(row)
        except ApiError as exc:
            if not self.should_retry_sub2api_session(row, exc):
                raise
        row = self.ensure_sub2api_session(channel_id, row, turnstile_token, force_refresh=True)
        return row, call(row)


    def _apply_balance_result(self, channel_id: int, row: sqlite3.Row, result: dict[str, Any], *, notify: bool = True) -> None:
        remaining = optional_float(result.get("remaining"))
        threshold = optional_float(row["threshold"]) or 0
        status = "warning" if remaining is not None and threshold > 0 and remaining < threshold else "healthy"
        now = utc_now()
        unit = result.get("unit") or row["unit"] or "USD"
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE channels
                SET balance = ?, unit = ?, quota_total = ?, used = ?, status = ?,
                    last_error = NULL, last_checked_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    remaining,
                    unit,
                    optional_float(result.get("total")),
                    optional_float(result.get("used")),
                    status,
                    now,
                    now,
                    channel_id,
                ),
            )
            if row["is_account_parent"]:
                conn.execute(
                    """
                    UPDATE channels
                    SET balance = NULL, quota_total = NULL, used = NULL, unit = ?,
                        status = 'never', last_error = NULL, last_checked_at = NULL, updated_at = ?
                    WHERE source_channel_id = ?
                    """,
                    (unit, now, channel_id),
                )
            conn.execute(
                """
                INSERT INTO history (channel_id, kind, status, remaining, payload_json, created_at)
                VALUES (?, 'balance', 'valid', ?, ?, ?)
                """,
                (channel_id, remaining, json.dumps(result, ensure_ascii=False), now),
            )
        if status == "warning":
            event_state = self.ensure_event(
                channel_id,
                "low_balance",
                "warning",
                f"{row['name']} 余额低于阈值",
                f"当前余额 {remaining:g} {unit}，阈值 {threshold:g} {unit}。",
            )
            if notify and event_state:
                self.notify_event(event_state["event"])
        else:
            self.resolve_event(channel_id, "low_balance")
        self.resolve_event(channel_id, "probe_failed")
        self.maybe_pool_schedule(channel_id, notify=notify)

    def _record_probe_failure(self, channel_id: int, row: sqlite3.Row, message: str, *, kind: str = "balance") -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE channels
                SET status = 'offline', last_error = ?, last_checked_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (message, now, now, channel_id),
            )
            conn.execute(
                """
                INSERT INTO history (channel_id, kind, status, payload_json, created_at)
                VALUES (?, ?, 'invalid', ?, ?)
                """,
                (channel_id, kind, json.dumps({"error": message}, ensure_ascii=False), now),
            )
        self.ensure_event(channel_id, "probe_failed", "critical", f"{row['name']} 探测失败", message)
        self.maybe_pool_schedule(channel_id)
