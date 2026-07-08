from __future__ import annotations

import sqlite3
from pathlib import Path

from apps.api.app.core.utils import utc_now


class SchemaMixin:
    def __init__(self, path: Path, *, seed_demo: bool = False) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init(seed_demo=seed_demo)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init(self, *, seed_demo: bool = False) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    platform TEXT NOT NULL CHECK(platform IN ('newApi', 'sub2Api')),
                    base_url TEXT NOT NULL,
                    model_scope TEXT,
                    group_id TEXT,
                    group_name TEXT,
                    rate_multiplier REAL,
                    threshold REAL NOT NULL DEFAULT 10,
                    balance REAL,
                    unit TEXT NOT NULL DEFAULT 'USD',
                    quota_total REAL,
                    used REAL,
                    status TEXT NOT NULL DEFAULT 'never',
                    last_error TEXT,
                    last_checked_at TEXT,
                    api_key TEXT,
                    api_key_masked TEXT,
                    access_token TEXT,
                    refresh_token TEXT,
                    user_id TEXT,
                    email TEXT,
                    password TEXT,
                    is_enabled INTEGER NOT NULL DEFAULT 1,
                    is_demo INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
                    type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    is_ack INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    acked_at TEXT
                );

                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER REFERENCES channels(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    remaining REAL,
                    rate_multiplier REAL,
                    payload_json TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS channel_groups (
                    channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
                    group_id TEXT NOT NULL,
                    group_name TEXT,
                    rate_multiplier REAL,
                    payload_json TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (channel_id, group_id)
                );

                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS qqbot_subscribers (
                    target_type TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    source_event TEXT,
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    is_enabled INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (target_type, target_id)
                );
                """
            )
            self.ensure_column(conn, "channels", "external_key_id", "TEXT")
            self.ensure_column(conn, "channels", "key_name", "TEXT")
            self.ensure_column(conn, "channels", "key_provider", "TEXT")
            self.ensure_column(conn, "channels", "api_key_masked", "TEXT")
            self.ensure_column(conn, "channels", "source_channel_id", "INTEGER REFERENCES channels(id) ON DELETE SET NULL")
            self.ensure_column(conn, "channels", "is_account_parent", "INTEGER NOT NULL DEFAULT 0")
            self.ensure_column(conn, "channels", "is_default_key", "INTEGER NOT NULL DEFAULT 0")
            self.ensure_column(conn, "channels", "is_monitoring", "INTEGER NOT NULL DEFAULT 0")
            self.ensure_column(conn, "channels", "monitor_models", "TEXT")
            self.ensure_column(conn, "channels", "monitor_interval_seconds", "INTEGER NOT NULL DEFAULT 60")
            self.ensure_column(conn, "channels", "monitor_status", "TEXT NOT NULL DEFAULT 'idle'")
            self.ensure_column(conn, "channels", "monitor_last_checked_at", "TEXT")
            self.ensure_column(conn, "channels", "monitor_last_error", "TEXT")
            self.ensure_column(conn, "channels", "monitor_latency_ms", "INTEGER")
            self.ensure_column(conn, "channels", "monitor_result_json", "TEXT")
            self.ensure_column(conn, "channels", "disable_on_rate_multiplier_change", "INTEGER NOT NULL DEFAULT 0")
            self.ensure_column(conn, "channels", "disable_on_model_sync_failure", "INTEGER NOT NULL DEFAULT 0")
            self.ensure_column(conn, "channels", "scheduling_disabled_reason", "TEXT")
            # 号池自动调度（Pool Auto Scheduler）——上游 channel 映射到我方 sub2api 号池账号
            self.ensure_column(conn, "channels", "pool_account_ids", "TEXT")
            self.ensure_column(conn, "channels", "pool_rate_threshold", "REAL")
            self.ensure_column(conn, "channels", "pool_sell_rate", "REAL")
            self.ensure_column(conn, "channels", "pool_target_margin", "REAL")
            self.ensure_column(conn, "channels", "pool_last_priority", "INTEGER")
            self.ensure_column(conn, "channels", "pool_auto_schedule", "INTEGER NOT NULL DEFAULT 1")
            self.ensure_column(conn, "channels", "pool_desired_state", "TEXT")
            self.ensure_column(conn, "channels", "pool_last_pushed_state", "TEXT")
            self.ensure_column(conn, "channels", "pool_recover_streak", "INTEGER NOT NULL DEFAULT 0")
            self.ensure_column(conn, "channels", "pool_last_reason", "TEXT")
            self.ensure_column(conn, "channels", "pool_last_error", "TEXT")
            self.ensure_column(conn, "channels", "pool_last_pushed_at", "TEXT")
            self.ensure_column(conn, "events", "notified_at", "TEXT")
            self.normalize_channel_hierarchy(conn)
            count = conn.execute("SELECT COUNT(*) AS count FROM channels").fetchone()["count"]
            if seed_demo and count == 0:
                self._seed(conn)

    def ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def normalize_channel_hierarchy(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            UPDATE channels
            SET is_account_parent = 0
            WHERE source_channel_id IS NOT NULL
               OR (
                   source_channel_id IS NULL
                   AND api_key IS NOT NULL
                   AND NOT EXISTS (
                       SELECT 1
                       FROM channels child
                       WHERE child.source_channel_id = channels.id
                   )
               )
            """
        )
        conn.execute(
            """
            UPDATE channels AS parent
            SET is_account_parent = 1
            WHERE parent.source_channel_id IS NULL
              AND (parent.access_token IS NOT NULL OR parent.refresh_token IS NOT NULL OR parent.email IS NOT NULL)
              AND (
                parent.api_key IS NULL
                OR EXISTS (SELECT 1 FROM channels child WHERE child.source_channel_id = parent.id)
              )
            """
        )
        conn.execute(
            """
            UPDATE channels
            SET is_default_key = 1
            WHERE id IN (
                SELECT MIN(child.id)
                FROM channels parent
                JOIN channels child ON child.source_channel_id = parent.id
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM channels existing
                    WHERE existing.source_channel_id = parent.id
                      AND existing.is_default_key = 1
                )
                GROUP BY parent.id
            )
            """
        )

    def _seed(self, conn: sqlite3.Connection) -> None:
        now = utc_now()
        rows = [
            {
                "name": "Production Router",
                "platform": "sub2Api",
                "base_url": "https://sub2api.demo.local",
                "model_scope": "Claude / Codex",
                "group_id": "pro",
                "group_name": "Pro Plan",
                "rate_multiplier": 0.8,
                "threshold": 10,
                "balance": 42.18,
                "quota_total": 60,
                "status": "healthy",
                "api_key": "sub2_live_router_w6Q",
            },
            {
                "name": "Staging Lab",
                "platform": "newApi",
                "base_url": "https://newapi.demo.local",
                "model_scope": "Gemini / Codex",
                "group_id": "gemini",
                "group_name": "Gemini Team",
                "rate_multiplier": 1.2,
                "threshold": 10,
                "balance": 8.42,
                "quota_total": 40,
                "status": "warning",
                "access_token": "newapi_test_stage_nT31",
                "user_id": "42",
            },
            {
                "name": "Mobile Client",
                "platform": "sub2Api",
                "base_url": "https://mobile.demo.local",
                "model_scope": "All models",
                "group_id": "legacy",
                "group_name": "Legacy Pool",
                "threshold": 20,
                "status": "offline",
                "last_error": "accessToken 已过期",
                "api_key": "sub2_live_mobile_C0aB",
            },
            {
                "name": "Codex Overflow",
                "platform": "newApi",
                "base_url": "https://codex.demo.local",
                "model_scope": "Codex",
                "group_id": "codex",
                "group_name": "Codex Pro",
                "rate_multiplier": 0.6,
                "threshold": 20,
                "balance": 116.4,
                "quota_total": 180,
                "status": "healthy",
                "access_token": "newapi_live_codex_K9xP",
                "user_id": "108",
            },
        ]
        for item in rows:
            conn.execute(
                """
                INSERT INTO channels (
                    name, platform, base_url, model_scope, group_id, group_name, rate_multiplier,
                    threshold, balance, quota_total, status, last_error, api_key, access_token,
                    user_id, is_demo, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    item["name"],
                    item["platform"],
                    item["base_url"],
                    item.get("model_scope"),
                    item.get("group_id"),
                    item.get("group_name"),
                    item.get("rate_multiplier"),
                    item["threshold"],
                    item.get("balance"),
                    item.get("quota_total"),
                    item["status"],
                    item.get("last_error"),
                    item.get("api_key"),
                    item.get("access_token"),
                    item.get("user_id"),
                    now,
                    now,
                ),
            )
        conn.execute(
            """
            INSERT INTO events (channel_id, type, severity, title, message, created_at)
            VALUES (2, 'low_balance', 'warning', 'Staging Lab 余额低于阈值', '当前余额 $8.42，阈值 $10。', ?)
            """,
            (now,),
        )
        conn.execute(
            """
            INSERT INTO events (channel_id, type, severity, title, message, created_at)
            VALUES (3, 'probe_failed', 'critical', 'Mobile Client 探测失败', 'accessToken 已过期，请更新凭证后重试。', ?)
            """,
            (now,),
        )
