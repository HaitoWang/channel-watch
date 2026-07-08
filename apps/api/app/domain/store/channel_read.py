from __future__ import annotations

import sqlite3
from typing import Any


class ChannelReadMixin:
    active_channel_filter = """
        NOT (
            c.platform = 'sub2Api'
            AND c.api_key IS NULL
            AND c.external_key_id IS NULL
            AND (c.access_token IS NOT NULL OR c.refresh_token IS NOT NULL OR c.email IS NOT NULL)
            AND EXISTS (
                SELECT 1
                FROM channels child
                WHERE child.source_channel_id = c.id
                  AND (child.api_key IS NOT NULL OR child.external_key_id IS NOT NULL)
            )
        )
    """

    def list_channels(self, status: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT c.*
                FROM channels c
                WHERE {self.active_channel_filter}
                ORDER BY CASE c.status
                    WHEN 'offline' THEN 0
                    WHEN 'warning' THEN 1
                    WHEN 'never' THEN 2
                    WHEN 'healthy' THEN 3
                    ELSE 4
                END, c.name
                """
            ).fetchall()
        channels = [self.public_channel(row) for row in rows]
        if status and status != "all":
            channels = [item for item in channels if item["status"] == status]
        return channels

    def get_channel_row(self, channel_id: int) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone()

    def list_channel_accounts(self, status: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM channels
                ORDER BY
                    CASE WHEN source_channel_id IS NULL THEN id ELSE source_channel_id END,
                    CASE WHEN source_channel_id IS NULL THEN 0 ELSE 1 END,
                    is_default_key DESC,
                    name COLLATE NOCASE
                """
            ).fetchall()
        by_parent: dict[int, list[sqlite3.Row]] = {}
        root_rows: list[sqlite3.Row] = []
        for row in rows:
            parent_id = row["source_channel_id"]
            if parent_id is None:
                root_rows.append(row)
            else:
                by_parent.setdefault(int(parent_id), []).append(row)

        accounts: list[dict[str, Any]] = []
        for row in root_rows:
            children = by_parent.get(int(row["id"]), [])
            if not children and not self.is_account_parent_row(row):
                children = [row]
            public_children = [self.public_channel(child) for child in children]
            if status and status != "all":
                public_children = [item for item in public_children if item["status"] == status]
            if status and status != "all" and not public_children:
                continue
            if len(public_children) == 1 and public_children[0]["id"] == row["id"] and not public_children[0].get("is_default_key"):
                public_children[0]["is_default_key"] = True
                public_children[0]["isDefaultKey"] = True
            parent = self.public_channel(row)
            parent["children"] = public_children
            parent["child_count"] = len(public_children)
            parent["childCount"] = len(public_children)
            parent["monitoring_count"] = sum(1 for item in public_children if item.get("is_monitoring") or item.get("isMonitoring"))
            parent["monitoringCount"] = parent["monitoring_count"]
            parent["default_child_id"] = next((item["id"] for item in public_children if item.get("is_default_key") or item.get("isDefaultKey")), None)
            parent["defaultChildId"] = parent["default_child_id"]
            accounts.append(parent)
        return accounts

    def enabled_channel_ids(self) -> list[int]:
        # 余额探测覆盖所有父账号（含已停止调度的）：禁用调度不等于停止监控
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT c.id
                FROM channels c
                WHERE c.source_channel_id IS NULL
                ORDER BY c.id
                """
            ).fetchall()
        return [int(row["id"]) for row in rows]
