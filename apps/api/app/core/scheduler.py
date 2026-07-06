from __future__ import annotations

import threading
from collections.abc import Callable

from apps.api.app.domain.store import RadarStore


def start_periodic_task(
    name: str,
    label: str,
    interval_seconds: int,
    callback: Callable[[], None],
    *,
    run_immediately: bool = True,
) -> threading.Event:
    stop_event = threading.Event()
    if interval_seconds <= 0:
        print(f"{label} disabled", flush=True)
        return stop_event

    def run() -> None:
        print(f"{label} enabled: every {interval_seconds}s", flush=True)
        while not stop_event.is_set():
            if not run_immediately and stop_event.wait(interval_seconds):
                break
            try:
                callback()
            except Exception as exc:
                print(f"[{name}] scheduled task failed: {exc}", flush=True)
            if not run_immediately:
                continue
            if stop_event.wait(interval_seconds):
                break

    thread = threading.Thread(target=run, name=f"channel-radar-{name}", daemon=True)
    thread.start()
    return stop_event


def start_auto_probe(store: RadarStore, interval_seconds: int) -> threading.Event:
    return start_periodic_task("auto-probe", "Auto probe", interval_seconds, store.auto_probe_once)


def start_model_monitor(store: RadarStore, interval_seconds: int) -> threading.Event:
    return start_periodic_task("model-monitor", "Model monitor", interval_seconds, store.auto_model_probe_once)


def start_unified_monitor(
    store: RadarStore,
    interval_seconds: int,
    *,
    include_balance: bool = True,
    include_rate: bool = True,
    include_model: bool = True,
) -> threading.Event:
    return start_periodic_task(
        "unified-monitor",
        "Unified monitor",
        interval_seconds,
        lambda: store.unified_monitor_scan_once(include_balance=include_balance, include_rate=include_rate, include_model=include_model),
        run_immediately=False,
    )


def start_rate_probe(store: RadarStore, interval_seconds: int) -> threading.Event:
    return start_periodic_task("rate-probe", "Rate probe", interval_seconds, store.auto_group_probe_once)


def start_pool_scheduler(store: RadarStore, *, default_interval: int = 120) -> threading.Event:
    """号池自动调度独立定时器。

    每一轮都动态重读号池配置（pool_enabled / pool_scan_interval），
    因此在设置页修改开关或周期后无需重启即可生效。周期为 0 表示暂停轮询
    （但探测点触发的即时调度仍然有效）。
    """
    stop_event = threading.Event()

    def run() -> None:
        print("Pool scheduler thread started", flush=True)
        while not stop_event.is_set():
            interval = default_interval
            try:
                config = store.pool_config()
                interval = int(config.get("scan_interval") or default_interval)
                if config.get("enabled") and interval > 0:
                    result = store.schedule_all_pool_channels()
                    changed = result.get("changed", 0)
                    if changed:
                        print(f"[pool-scheduler] {changed} channel(s) toggled", flush=True)
            except Exception as exc:  # noqa: BLE001 —— 单轮失败不终止定时器
                print(f"[pool-scheduler] scan failed: {exc}", flush=True)
            # 周期无效（0 或未开启）时回落到温和的重查间隔，等待配置被开启
            wait_seconds = interval if interval and interval > 0 else max(30, default_interval)
            if stop_event.wait(wait_seconds):
                break

    thread = threading.Thread(target=run, name="channel-radar-pool-scheduler", daemon=True)
    thread.start()
    return stop_event


def start_balance_rate_scan(
    store: RadarStore,
    interval_seconds: int,
    *,
    include_balance: bool = True,
    include_rate: bool = True,
) -> threading.Event:
    return start_periodic_task(
        "balance-rate-scan",
        "Balance/rate scan",
        interval_seconds,
        lambda: store.auto_balance_rate_scan_once(include_balance=include_balance, include_rate=include_rate),
    )
