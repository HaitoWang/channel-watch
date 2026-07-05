from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
DB_PATH = ROOT / "data" / "radar.db"
DEFAULT_TIMEOUT = 18
DEFAULT_BALANCE_RATE_SCAN_INTERVAL = 60
DEFAULT_AUTO_PROBE_INTERVAL = DEFAULT_BALANCE_RATE_SCAN_INTERVAL
DEFAULT_RATE_PROBE_INTERVAL = DEFAULT_BALANCE_RATE_SCAN_INTERVAL
DEFAULT_MODEL_MONITOR_INTERVAL = 60
DEFAULT_UPSTREAM_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
}


@dataclass(frozen=True)
class ApiSettings:
    host: str = "127.0.0.1"
    port: int = 4176
    data_dir: Path = ROOT / "data"
    balance_rate_scan_interval: int = DEFAULT_BALANCE_RATE_SCAN_INTERVAL
    auto_probe_interval: int = DEFAULT_BALANCE_RATE_SCAN_INTERVAL
    rate_probe_interval: int = DEFAULT_BALANCE_RATE_SCAN_INTERVAL
    model_monitor_interval: int = 60
