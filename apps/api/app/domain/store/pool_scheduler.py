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
from apps.api.app.infrastructure.integrations.pool_sub2api import set_account_priority, set_account_schedulable


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
            "sell_rate_default": optional_float(settings.get("pool_sell_rate")),
            "target_margin_default": optional_float(settings.get("pool_target_margin")),
            "auto_priority": bool(settings.get("pool_auto_priority")),
            "burnout_warn_hours": optional_float(settings.get("pool_burnout_warn_hours")),
            "slow_ttft_seconds": optional_float(settings.get("pool_slow_ttft_seconds")),
            "slow_count": int(settings.get("pool_slow_count") or 5),
            "slow_sample": int(settings.get("pool_slow_sample") or 10),
            "slow_min_sample": int(settings.get("pool_slow_min_sample") or 5),
        }

    @staticmethod
    def _margin_threshold(sell_rate: float | None, target_margin: float | None) -> float | None:
        """毛利护栏公式：有效倒挂阈值 = 卖价 ÷ (1 + 目标毛利率)。

        卖价按倍率计（如 2.0），目标毛利率按百分数（如 20 表示 20%）。
        上游倍率超过此阈值即毛利跌破目标，应禁用。
        """
        if sell_rate is None or sell_rate <= 0:
            return None
        margin = (target_margin or 0) / 100.0
        if margin <= -1:
            return None
        return sell_rate / (1 + margin)

    def resolve_rate_threshold(self, row: sqlite3.Row, config: dict[str, Any]) -> float | None:
        """按优先级解析该 Key 的倒挂阈值：
        1) Key 绝对阈值  2) Key 卖价/毛利算出  3) 全局卖价/毛利算出  4) 全局绝对阈值。"""
        explicit = optional_float(row["pool_rate_threshold"])
        if explicit is not None:
            return explicit
        key_calc = self._margin_threshold(
            optional_float(row["pool_sell_rate"]),
            optional_float(row["pool_target_margin"]),
        )
        if key_calc is not None:
            return key_calc
        global_calc = self._margin_threshold(config.get("sell_rate_default"), config.get("target_margin_default"))
        if global_calc is not None:
            return global_calc
        return config.get("rate_threshold_default")

    def current_margin(self, row: sqlite3.Row, config: dict[str, Any]) -> float | None:
        """当前毛利率 %（基于该 Key 有效卖价与上游倍率）：(卖价-成本)/卖价。"""
        sell = optional_float(row["pool_sell_rate"]) or config.get("sell_rate_default")
        cost = optional_float(row["rate_multiplier"])
        if not sell or sell <= 0 or cost is None:
            return None
        return round((sell - cost) / sell * 100, 1)

    def estimate_burn_hours(self, channel_id: int) -> dict[str, Any] | None:
        """根据 history 近若干条余额点估算燃尽时间。

        取最近 ≤20 条 balance 记录，按时间正序，用净消耗（余额下降）算平均
        速率（USD/小时）。滤掉充值造成的余额突增。数据不足则返回 None（不误报）。
        返回 {hours, rate_per_hour, current}。
        """
        from datetime import datetime

        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT remaining, created_at
                FROM history
                WHERE channel_id = ? AND kind = 'balance' AND remaining IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 20
                """,
                (channel_id,),
            ).fetchall()
        points: list[tuple[datetime, float]] = []
        for r in rows:
            try:
                ts = datetime.fromisoformat(str(r["created_at"]))
            except (ValueError, TypeError):
                continue
            points.append((ts, float(r["remaining"])))
        if len(points) < 3:
            return None
        points.reverse()  # 时间正序

        # 累加"下降段"消耗与时长；余额上升（充值）跳过
        spent = 0.0
        hours = 0.0
        for (t0, b0), (t1, b1) in zip(points, points[1:]):
            dt = (t1 - t0).total_seconds() / 3600.0
            if dt <= 0:
                continue
            drop = b0 - b1
            if drop > 0:  # 只统计净消耗
                spent += drop
                hours += dt
        if hours <= 0 or spent <= 0:
            return None
        rate = spent / hours  # USD/小时
        current = points[-1][1]
        if rate <= 0:
            return None
        return {
            "hours": round(current / rate, 1),
            "rate_per_hour": round(rate, 4),
            "current": current,
        }

    def maybe_burnout_warning(self, channel_id: int, row: sqlite3.Row, *, notify: bool = True) -> None:
        """余额燃尽预警：预计耗尽时间低于窗口则推送（父账号级）。"""
        config = self.pool_config()
        window = config.get("burnout_warn_hours")
        if not window or window <= 0:
            return
        est = self.estimate_burn_hours(channel_id)
        if not est:
            return
        if est["hours"] > window:
            self.resolve_event(channel_id, "balance_burnout")
            return
        unit = row["unit"] or "USD"
        daily = est["rate_per_hour"] * 24
        event_state = self.ensure_event(
            channel_id,
            "balance_burnout",
            "warning",
            f"{row['name']} 余额即将耗尽",
            f"余额预计 {est['hours']:g} 小时后耗尽（当前 {est['current']:g} {unit}，日耗 ~{daily:.0f} {unit}），建议充值。",
        )
        if notify and event_state:
            self.notify_event(event_state["event"])

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

    def _slow_ttft_reason(self, account_ids: list[str], config: dict[str, Any]) -> str | None:
        """首 token 慢检测：查该账号最近 N 次流式请求，超阈值次数达标则返回红信号。

        样本不足 / 未配置 / 查询失败 → 返回 None（不误杀）。
        """
        threshold_s = config.get("slow_ttft_seconds")
        if not threshold_s or threshold_s <= 0:
            return None
        if not account_ids:
            return None
        base = config.get("base_url")
        key = config.get("admin_api_key")
        if not base or not key:
            return None
        from apps.api.app.infrastructure.integrations.pool_sub2api import recent_first_token_ms

        sample = int(config.get("slow_sample") or 10)
        need_count = int(config.get("slow_count") or 5)
        min_sample = int(config.get("slow_min_sample") or 5)
        threshold_ms = threshold_s * 1000
        # 多个映射账号取最差的一个判定
        for account_id in account_ids:
            try:
                ttfts = recent_first_token_ms(base, key, account_id, sample)
            except Exception:  # noqa: BLE001 —— 查询失败不误杀
                continue
            if len(ttfts) < min_sample:
                continue  # 样本不足，跳过
            slow_n = sum(1 for x in ttfts if x > threshold_ms)
            if slow_n >= need_count:
                worst = max(ttfts) / 1000
                return f"首 token 慢：最近 {len(ttfts)} 次里 {slow_n} 次超 {threshold_s:g}s（最高 {worst:.0f}s）"
        return None

    def compute_pool_decision(self, row: sqlite3.Row, config: dict[str, Any]) -> dict[str, Any]:
        """纯计算：返回目标态、原因、下一轮 streak，不做任何写入或下发。"""
        channel = self.pool_channel_settings(row)
        # 阈值优先级：Key 绝对阈值 → Key 卖价/毛利 → 全局卖价/毛利 → 全局绝对阈值
        rate_threshold = self.resolve_rate_threshold(row, config)

        reasons = self._pool_signals(row, rate_threshold)
        # 首 token 慢检测（账号级，需查我方 sub2api 用量记录；失败/样本不足不误杀）
        slow_reason = self._slow_ttft_reason(channel["account_ids"], config)
        if slow_reason:
            reasons.append(slow_reason)
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
            # 真正下发了开关时，同步本地 is_enabled，保持界面与号池一致：
            # 启用 → is_enabled=1 且清除停调原因；禁用 → is_enabled=0。
            if pushed_state == "enabled":
                assignments.append("is_enabled = 1")
                assignments.append("scheduling_disabled_reason = NULL")
            elif pushed_state == "disabled":
                assignments.append("is_enabled = 0")
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
        # 本分支只在「实际翻转下发」时执行；先关闭旧的调度事件，确保启用⇄禁用
        # 每次翻转都生成新事件并重新通知（否则复用旧事件会被 notified_at 去重挡掉）。
        self.resolve_event(channel_id, "pool_scheduled")
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
        reorder = None
        if config.get("auto_priority"):
            try:
                reorder = self.reorder_pool_priority(config)
            except Exception as exc:  # noqa: BLE001
                reorder = {"ok": False, "error": str(exc)}
        return {"ok": True, "evaluated": len(results), "changed": changed, "results": results, "reorder": reorder}

    def reorder_pool_priority(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        """按成本给「健康且启用」的号池账号排序 priority：倍率升序（次要按模型延迟），
        最便宜的排最前（priority 最小）。步长 10 留插入空间，仅在变化时下发（幂等）。"""
        config = config or self.pool_config()
        if not config.get("base_url") or not config.get("admin_api_key"):
            return {"ok": False, "error": "号池连接未配置"}

        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, pool_account_ids, rate_multiplier, monitor_latency_ms,
                       pool_last_pushed_state, pool_last_priority
                FROM channels
                WHERE pool_account_ids IS NOT NULL
                  AND TRIM(pool_account_ids) != ''
                  AND pool_auto_schedule = 1
                """
            ).fetchall()

        # 只排「未被禁用」的（禁用态账号已关停，不参与成本排序）
        candidates = []
        for r in rows:
            if r["pool_last_pushed_state"] == "disabled":
                continue
            rate = optional_float(r["rate_multiplier"])
            if rate is None:
                continue  # 倍率未知不参与排序，避免脏数据
            latency = r["monitor_latency_ms"] if r["monitor_latency_ms"] is not None else 10**9
            for account_id in parse_account_ids(r["pool_account_ids"]):
                candidates.append({
                    "channel_id": int(r["id"]),
                    "account_id": account_id,
                    "rate": rate,
                    "latency": latency,
                    "last_priority": r["pool_last_priority"],
                })
        # 成本升序 → 延迟升序
        candidates.sort(key=lambda c: (c["rate"], c["latency"]))

        pushed = 0
        errors: list[str] = []
        seen_channels: dict[int, int] = {}
        for idx, c in enumerate(candidates):
            priority = (idx + 1) * 10
            if c["last_priority"] == priority:
                seen_channels.setdefault(c["channel_id"], priority)
                continue  # 幂等：未变化不下发
            try:
                set_account_priority(config["base_url"], config["admin_api_key"], c["account_id"], priority)
                pushed += 1
                seen_channels[c["channel_id"]] = priority
            except ApiError as exc:
                errors.append(f"账号 {c['account_id']}: {exc.message}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"账号 {c['account_id']}: {exc}")
        # 记录每个 channel 最新下发的 priority（用最小值代表）
        now = utc_now()
        with self.connect() as conn:
            for channel_id, priority in seen_channels.items():
                conn.execute(
                    "UPDATE channels SET pool_last_priority = ?, updated_at = ? WHERE id = ?",
                    (priority, now, channel_id),
                )
        return {"ok": not errors, "ranked": len(candidates), "pushed": pushed, "errors": errors}

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
