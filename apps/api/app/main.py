from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer

from .api.handler import ApiHandler
from .core.config import DB_PATH, DEFAULT_BALANCE_RATE_SCAN_INTERVAL
from .core.scheduler import start_unified_monitor
from .domain.store import RadarStore
from .infrastructure.integrations.qqbot_gateway import start_qqbot_gateway


def main() -> None:
    parser = argparse.ArgumentParser(description="Channel Radar API backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4176)
    parser.add_argument("--seed-demo", action="store_true", help="空库启动时写入演示渠道数据")
    parser.add_argument(
        "--balance-rate-scan-interval",
        "--scan-interval",
        dest="balance_rate_scan_interval",
        type=int,
        default=DEFAULT_BALANCE_RATE_SCAN_INTERVAL,
        help="余额、倍率、模型状态统一监控间隔秒数，默认 60 秒",
    )
    parser.add_argument("--no-balance-rate-scan", action="store_true", help="关闭后台余额和倍率扫描")
    parser.add_argument("--auto-probe-interval", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--no-auto-probe", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--rate-probe-interval", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--no-rate-probe", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--model-monitor-interval", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--no-model-monitor", action="store_true", help="关闭后台模型监控")
    args = parser.parse_args()

    ApiHandler.store = RadarStore(DB_PATH, seed_demo=args.seed_demo)
    legacy_intervals = [value for value in (args.auto_probe_interval, args.rate_probe_interval, args.model_monitor_interval) if value is not None]
    scan_interval = min(legacy_intervals) if legacy_intervals else args.balance_rate_scan_interval
    include_balance = not args.no_balance_rate_scan and not args.no_auto_probe
    include_rate = not args.no_balance_rate_scan and not args.no_rate_probe
    include_model = not args.no_model_monitor
    stop_unified_monitor = start_unified_monitor(
        ApiHandler.store,
        0 if not (include_balance or include_rate or include_model) else scan_interval,
        include_balance=include_balance,
        include_rate=include_rate,
        include_model=include_model,
    )
    stop_qqbot_gateway = start_qqbot_gateway(ApiHandler.store)
    server = ThreadingHTTPServer((args.host, args.port), ApiHandler)
    print(f"Channel Radar API running at http://{args.host}:{args.port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_unified_monitor.set()
        stop_qqbot_gateway.set()
        server.server_close()


if __name__ == "__main__":
    main()
