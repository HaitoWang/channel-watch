"""号池自动调度决策（Pool Auto Scheduler）。

根据上游 channel 的实时指标（分组倍率、账号余额、模型可用性、探测状态），
计算我方 sub2api 号池对应账号的期望调度态，并在期望态翻转时下发开关。

设计要点：
- 三个总开关：全局 pool_enabled（功能开关）、全局 pool_auto_schedule（是否真实下发，
  关闭即 dry-run 只记录不调用）、channel.pool_auto_schedule（该渠道是否参与）。
- 触发条件（任一命中即“禁用”）：倍率高于阈值 / 余额低于阈值或耗尽 /
  上游模型探测异常 / 探测请求失败。
- 防横跳：命中即时禁用；全绿需连续 N 轮（pool_recover_stable_rounds）才启用。
- 幂等：仅当目标态与上次已下发态不同才调用我方接口。
- 失败保留：下发失败记录 pool_last_error 并保持已下发态，下一轮自动重试。
"""

from __future__ import annotations

import sqlite3
from typing import Any

from apps.api.app.core.errors import ApiError
from apps.api.app.core.utils import bool_value, optional_float, utc_now
from apps.api.app.infrastructure.integrations.pool_sub2api import set_account_schedulable


def parse_account_ids(value: Any) -> list[str]:
    """把逗号分隔（或数组）的号池账号 ID 规整为去重、保序的字符串列表。"""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        raw = [str(item) for item in value]
    else:
        raw = str(value).replace("，", ",").split(",")
    result: list[str] = []
    for item in raw:
        token = item.strip()
        if token and token not in result:
            result.append(token)
    return result


class PoolSchedulerMixin:
    def pool_config(self) -> dict[str, Any]:
        settings = self.sub2api_settings(include_secret=True)
        return {
            "enabled": bool(settings.get("pool_enabled")),
            "auto_schedule": bool(settings.get("pool_auto_schedule")),
            "base_url": settings.get("pool_base_url") or "",
            "admin_api_key": settings.get("pool_admin_api_key") or "",
            "recover_rounds": int(settings.get("pool_recover_stable_rounds") or 2),
            "rate_threshold_default": optional_float(settings.get("pool_rate_threshold_default")),
            "scan_interval": int(settings.get("pool_scan_interval") or 120),
        }

    def pool_channel_settings(self, row: sqlite3.Row) -> dict[str, Any]:
        account_ids = parse_account_ids(row["pool_account_ids"])
        return {
            "account_ids": account_ids,
            "auto_schedule": bool(row["pool_auto_schedule"]),
            "rate_threshold": optional_float(row["pool_rate_threshold"]),
        }

    def _balance_row_for(self, row: sqlite3.Row) -> sqlite3.Row:
        """余额是父账号级：子 Key 取其父账号的余额行，父账号取自身。"""
        parent_id = row["source_channel_id"]
        if parent_id is None:
            return row
        parent = self.get_channel_row(int(parent_id))
        return parent or row

    def _pool_signals(self, row: sqlite3.Row, rate_threshold: float | None) -> list[str]:
        """返回触发禁用的红信号原因列表（空列表代表全绿）。

        倍率 / 模型可用性读 Key 自身；余额从父账号取（账号级共享）。
        """
        reasons: list[str] = []

        rate = optional_float(row["rate_multiplier"])
        if rate is not None and rate_threshold is not None and rate_threshold > 0 and rate > rate_threshold:
            reasons.append(f"倍率 {rate:g} 高于阈值 {rate_threshold:g}（价格倒挂）")

        balance_row = self._balance_row_for(row)
        balance = optional_float(balance_row["balance"])
        threshold = optional_float(balance_row["threshold"]) or 0
        if balance is not None:
            if balance <= 0:
                reasons.append("上游余额已耗尽")
            elif threshold > 0 and balance < threshold:
                reasons.append(f"上游余额 {balance:g} 低于阈值 {threshold:g}")

        monitor_status = str(row["monitor_status"] or "").strip().lower()
        if monitor_status == "error" or row["monitor_last_error"]:
            detail = row["monitor_last_error"] or "模型探测异常"
            reasons.append(f"上游模型探测异常：{detail}")

        status = str(row["status"] or "").strip().lower()
        if status == "offline" or row["last_error"]:
            detail = row["last_error"] or "探测请求失败"
            reasons.append(f"探测失败：{detail}")

        return reasons

    def compute_pool_decision(self, row: sqlite3.Row, config: dict[str, Any]) -> dict[str, Any]:
        """纯计算：返回目标态、原因、下一轮 streak，不做任何写入或下发。"""
        channel = self.pool_channel_settings(row)
        rate_threshold = channel["rate_threshold"]
        if rate_threshold is None:
            rate_threshold = config.get("rate_threshold_default")

        reasons = self._pool_signals(row, rate_threshold)
        current_streak = int(row["pool_recover_streak"] or 0)
        last_pushed = row["pool_last_pushed_state"]
        recover_rounds = max(1, int(config.get("recover_rounds") or 2))

        if reasons:
            target = "disabled"
            next_streak = 0
            reason_text = "；".join(reasons)
        else:
            next_streak = current_streak + 1
            if next_streak >= recover_rounds:
                target = "enabled"
                reason_text = f"指标连续 {next_streak} 轮正常，恢复启用"
            else:
                # 尚未达到恢复轮数：维持上次已下发态，不翻转
                target = last_pushed
                reason_text = f"指标正常（{next_streak}/{recover_rounds} 轮），暂不恢复"

        return {
            "target": target,
            "reasons": reasons,
            "reason_text": reason_text,
            "next_streak": next_streak,
            "account_ids": channel["account_ids"],
            "rate_threshold": rate_threshold,
            "last_pushed": last_pushed,
            "auto_schedule": channel["auto_schedule"],
        }

    def _persist_pool_state(
        self,
        channel_id: int,
        *,
        desired_state: str | None,
        streak: int,
        reason: str | None,
        pushed_state: str | None = None,
        pushed_at: str | None = None,
        error: str | None = None,
    ) -> None:
        assignments = [
            "pool_desired_state = ?",
            "pool_recover_streak = ?",
            "pool_last_reason = ?",
            "pool_last_error = ?",
            "updated_at = ?",
        ]
        params: list[Any] = [desired_state, streak, reason, error, utc_now()]
        if pushed_state is not None:
            assignments.append("pool_last_pushed_state = ?")
            params.append(pushed_state)
        if pushed_at is not None:
            assignments.append("pool_last_pushed_at = ?")
            params.append(pushed_at)
        params.append(channel_id)
        with self.connect() as conn:
            conn.execute(f"UPDATE channels SET {', '.join(assignments)} WHERE id = ?", tuple(params))

    def evaluate_pool_schedule(
        self,
        channel_id: int,
        row: sqlite3.Row | None = None,
        *,
        notify: bool = True,
    ) -> dict[str, Any]:
        """核心入口：评估单个 channel 并在需要时下发号池账号开关。"""
        config = self.pool_config()
        if not config["enabled"]:
            return {"ok": True, "skipped": "pool_disabled"}

        if row is None:
            row = self.get_channel_row(channel_id)
        if not row:
            return {"ok": True, "skipped": "channel_missing"}

        decision = self.compute_pool_decision(row, config)
        if not decision["auto_schedule"]:
            return {"ok": True, "skipped": "channel_auto_schedule_off"}
        if not decision["account_ids"]:
            return {"ok": True, "skipped": "no_account_mapping"}

        target = decision["target"]
        last_pushed = decision["last_pushed"]

        # 目标态未定（尚未达到恢复轮数且从未下发）或与已下发态一致：仅持久化状态，不下发
        if target is None or target == last_pushed:
            self._persist_pool_state(
                channel_id,
                desired_state=target,
                streak=decision["next_streak"],
                reason=decision["reason_text"],
            )
            return {"ok": True, "changed": False, "target": target, "reason": decision["reason_text"]}

        enabled = target == "enabled"

        # dry-run：全局未开启实际下发，仅记录期望态
        if not config["auto_schedule"]:
            self._persist_pool_state(
                channel_id,
                desired_state=target,
                streak=decision["next_streak"],
                reason=f"[预览] {decision['reason_text']}（未实际下发）",
            )
            return {"ok": True, "changed": False, "dry_run": True, "target": target, "reason": decision["reason_text"]}

        # 实际下发到每个映射的号池账号
        errors: list[str] = []
        for account_id in decision["account_ids"]:
            try:
                set_account_schedulable(config["base_url"], config["admin_api_key"], account_id, enabled)
            except ApiError as exc:
                errors.append(f"账号 {account_id}: {exc.message}")
            except Exception as exc:  # noqa: BLE001 —— 兜底任何下发异常，保证调度循环不中断
                errors.append(f"账号 {account_id}: {exc}")

        action = "启用" if enabled else "禁用"
        if errors:
            error_text = "；".join(errors)
            self._persist_pool_state(
                channel_id,
                desired_state=target,
                streak=decision["next_streak"],
                reason=decision["reason_text"],
                error=error_text,
            )
            event_state = self.ensure_event(
                channel_id,
                "pool_schedule_failed",
                "critical",
                f"{row['name']} 号池调度下发失败",
                f"目标{action}号池账号失败：{error_text}",
            )
            if notify and event_state:
                self.notify_event(event_state["event"])
            return {"ok": False, "changed": False, "target": target, "errors": errors}

        now = utc_now()
        self._persist_pool_state(
            channel_id,
            desired_state=target,
            streak=decision["next_streak"],
            reason=decision["reason_text"],
            pushed_state=target,
            pushed_at=now,
            error=None,
        )
        self.resolve_event(channel_id, "pool_schedule_failed")
        severity = "info" if enabled else "warning"
        accounts_desc = "、".join(decision["account_ids"])
        event_state = self.ensure_event(
            channel_id,
            "pool_scheduled",
            severity,
            f"{row['name']} 已{action}号池账号",
            f"已{action}号池账号 [{accounts_desc}]。原因：{decision['reason_text']}",
        )
        if notify and event_state:
            self.notify_event(event_state["event"])
        return {
            "ok": True,
            "changed": True,
            "target": target,
            "accounts": decision["account_ids"],
            "reason": decision["reason_text"],
        }

    def maybe_pool_schedule(self, channel_id: int, *, notify: bool = True) -> None:
        """在探测收尾调用的安全包装：任何异常都不得中断探测主流程。"""
        try:
            self.evaluate_pool_schedule(channel_id, notify=notify)
        except Exception:  # noqa: BLE001 —— 调度失败不能影响探测本身
            pass

    def pool_schedule_preview(self, channel_id: int) -> dict[str, Any]:
        """dry-run 预览：只计算目标态与原因，不写库、不下发。"""
        config = self.pool_config()
        row = self.get_channel_row(channel_id)
        if not row:
            raise ApiError(404, "渠道不存在")
        decision = self.compute_pool_decision(row, config)
        return {
            "ok": True,
            "pool_enabled": config["enabled"],
            "auto_schedule": config["auto_schedule"],
            "channel_auto_schedule": decision["auto_schedule"],
            "account_ids": decision["account_ids"],
            "accountIds": decision["account_ids"],
            "current_state": decision["last_pushed"],
            "currentState": decision["last_pushed"],
            "target_state": decision["target"],
            "targetState": decision["target"],
            "reason": decision["reason_text"],
            "reasons": decision["reasons"],
            "rate_threshold": decision["rate_threshold"],
            "rateThreshold": decision["rate_threshold"],
            "recover_rounds": max(1, int(config.get("recover_rounds") or 2)),
            "recoverRounds": max(1, int(config.get("recover_rounds") or 2)),
        }

    def schedule_all_pool_channels(self, *, notify: bool = True) -> dict[str, Any]:
        """批量评估所有已映射号池账号的渠道（供定时/手动全量触发）。"""
        config = self.pool_config()
        if not config["enabled"]:
            return {"ok": True, "skipped": "pool_disabled", "results": []}
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id FROM channels
                WHERE pool_account_ids IS NOT NULL
                  AND TRIM(pool_account_ids) != ''
                  AND pool_auto_schedule = 1
                ORDER BY id
                """
            ).fetchall()
        results = []
        for item in rows:
            channel_id = int(item["id"])
            try:
                outcome = self.evaluate_pool_schedule(channel_id, notify=notify)
            except ApiError as exc:
                outcome = {"ok": False, "error": exc.message}
            results.append({"channel_id": channel_id, **outcome})
        changed = sum(1 for item in results if item.get("changed"))
        return {"ok": True, "evaluated": len(results), "changed": changed, "results": results}

    def enable_all_pool_accounts(self, *, notify: bool = True) -> dict[str, Any]:
        """一键启用：把所有已映射的号池账号强制置为可调度（无视指标信号）。

        用于「停止自动调度后，把之前被自动禁用的账号统一恢复」。不依赖
        pool_enabled 总开关（这是人工兜底动作），但仍需号池连接已配置。
        """
        config = self.pool_config()
        if not config["base_url"] or not config["admin_api_key"]:
            raise ApiError(400, "请先在设置页配置号池 Base URL 与 Admin API Key")

        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, pool_account_ids
                FROM channels
                WHERE pool_account_ids IS NOT NULL
                  AND TRIM(pool_account_ids) != ''
                ORDER BY id
                """
            ).fetchall()

        now = utc_now()
        enabled_count = 0
        account_count = 0
        errors: list[str] = []
        for item in rows:
            channel_id = int(item["id"])
            account_ids = parse_account_ids(item["pool_account_ids"])
            if not account_ids:
                continue
            channel_errors: list[str] = []
            for account_id in account_ids:
                try:
                    set_account_schedulable(config["base_url"], config["admin_api_key"], account_id, True)
                    account_count += 1
                except ApiError as exc:
                    channel_errors.append(f"账号 {account_id}: {exc.message}")
                except Exception as exc:  # noqa: BLE001 —— 单账号失败不中断整体
                    channel_errors.append(f"账号 {account_id}: {exc}")
            if channel_errors:
                error_text = "；".join(channel_errors)
                errors.append(f"{item['name']}: {error_text}")
                self._persist_pool_state(
                    channel_id,
                    desired_state="enabled",
                    streak=0,
                    reason="一键全部启用",
                    error=error_text,
                )
                event_state = self.ensure_event(
                    channel_id,
                    "pool_schedule_failed",
                    "critical",
                    f"{item['name']} 号池一键启用失败",
                    error_text,
                )
                if notify and event_state:
                    self.notify_event(event_state["event"])
            else:
                enabled_count += 1
                self._persist_pool_state(
                    channel_id,
                    desired_state="enabled",
                    streak=0,
                    reason="一键全部启用",
                    pushed_state="enabled",
                    pushed_at=now,
                    error=None,
                )
                self.resolve_event(channel_id, "pool_schedule_failed")
                self.resolve_event(channel_id, "pool_scheduled")
        return {
            "ok": not errors,
            "channels_enabled": enabled_count,
            "accounts_enabled": account_count,
            "errors": errors,
        }
