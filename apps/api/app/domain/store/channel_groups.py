from __future__ import annotations

import json
from typing import Any

from apps.api.app.core.utils import optional_float, utc_now
from apps.api.app.infrastructure.integrations import group_payload


class ChannelGroupMixin:
    def list_channel_groups(self, channel_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM channel_groups
                WHERE channel_id = ?
                ORDER BY
                    CASE WHEN rate_multiplier IS NULL THEN 1 ELSE 0 END,
                    rate_multiplier ASC,
                    group_name COLLATE NOCASE,
                    group_id
                """,
                (channel_id,),
            ).fetchall()
        return [
            {
                **group_payload(row["payload_json"]),
                "group_id": row["group_id"],
                "groupId": row["group_id"],
                "group_name": row["group_name"] or row["group_id"],
                "groupName": row["group_name"] or row["group_id"],
                "rate_multiplier": row["rate_multiplier"],
                "rateMultiplier": row["rate_multiplier"],
                "updated_at": row["updated_at"],
                "updatedAt": row["updated_at"],
            }
            for row in rows
        ]

    def store_channel_groups(self, channel_id: int, groups: list[dict[str, Any]]) -> None:
        now = utc_now()
        with self.connect() as conn:
            conn.execute("DELETE FROM channel_groups WHERE channel_id = ?", (channel_id,))
            for group in groups:
                group_id = str(group.get("group_id") or group.get("groupId") or "").strip()
                if not group_id:
                    continue
                group_name = str(group.get("group_name") or group.get("groupName") or group_id).strip()
                conn.execute(
                    """
                    INSERT OR REPLACE INTO channel_groups (
                        channel_id, group_id, group_name, rate_multiplier, payload_json, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                (
                        channel_id,
                        group_id,
                        group_name,
                        optional_float(group.get("rate_multiplier"))
                        if group.get("rate_multiplier") is not None
                        else optional_float(group.get("rateMultiplier")),
                        json.dumps(group, ensure_ascii=False),
                        now,
                    ),
                )
