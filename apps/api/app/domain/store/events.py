from __future__ import annotations

from typing import Any

from apps.api.app.core.errors import ApiError
from apps.api.app.infrastructure.integrations import history_payload_summary
from apps.api.app.core.utils import utc_now


class EventLogMixin:
    def ensure_event(self, channel_id: int, event_type: str, severity: str, title: str, message: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            existing = conn.execute(
                """
                SELECT id FROM events
                WHERE channel_id = ? AND type = ? AND is_ack = 0
                LIMIT 1
                """,
                (channel_id, event_type),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE events SET severity = ?, title = ?, message = ?, created_at = ? WHERE id = ?",
                    (severity, title, message, utc_now(), existing["id"]),
                )
                event = self.event_by_id(conn, int(existing["id"]))
                return {"created": False, "event": event}
            cursor = conn.execute(
                """
                INSERT INTO events (channel_id, type, severity, title, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (channel_id, event_type, severity, title, message, utc_now()),
            )
            event = self.event_by_id(conn, int(cursor.lastrowid))
            return {"created": True, "event": event}

    def resolve_event(self, channel_id: int, event_type: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE events
                SET is_ack = 1, acked_at = ?
                WHERE channel_id = ? AND type = ? AND is_ack = 0
                """,
                (utc_now(), channel_id, event_type),
            )

    def list_events(self, acknowledged: bool | None = None) -> list[dict[str, Any]]:
        where = ""
        params: tuple[Any, ...] = ()
        if acknowledged is not None:
            where = "WHERE e.is_ack = ?"
            params = (1 if acknowledged else 0,)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT e.*,
                       c.name AS channel_name,
                       c.platform,
                       c.key_name,
                       parent.name AS parent_name
                FROM events e
                LEFT JOIN channels c ON c.id = e.channel_id
                LEFT JOIN channels parent ON parent.id = c.source_channel_id
                {where}
                ORDER BY e.is_ack ASC, e.created_at DESC, e.id DESC
                """,
                params,
            ).fetchall()
        return [self.public_event(row) for row in rows]

    def event_by_id(self, conn: Any, event_id: int) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT e.*,
                   c.name AS channel_name,
                   c.platform,
                   c.key_name,
                   parent.name AS parent_name
            FROM events e
            LEFT JOIN channels c ON c.id = e.channel_id
            LEFT JOIN channels parent ON parent.id = c.source_channel_id
            WHERE e.id = ?
            """,
            (event_id,),
        ).fetchone()
        return self.public_event(row) if row else None

    def public_event(self, row: Any) -> dict[str, Any]:
        return {
            "id": row["id"],
            "channel_id": row["channel_id"],
            "channelId": row["channel_id"],
            "channel_name": row["channel_name"],
            "channelName": row["channel_name"],
            "key_name": row["key_name"],
            "keyName": row["key_name"],
            "parent_name": row["parent_name"],
            "parentName": row["parent_name"],
            "platform": row["platform"],
            "type": row["type"],
            "severity": row["severity"],
            "title": row["title"],
            "message": row["message"],
            "is_ack": bool(row["is_ack"]),
            "isAck": bool(row["is_ack"]),
            "created_at": row["created_at"],
            "createdAt": row["created_at"],
            "acked_at": row["acked_at"],
            "ackedAt": row["acked_at"],
            "notified_at": row["notified_at"],
            "notifiedAt": row["notified_at"],
        }

    def mark_event_notified(self, event_id: int) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE events SET notified_at = ? WHERE id = ?", (utc_now(), event_id))

    def ack_event(self, event_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            cursor = conn.execute(
                "UPDATE events SET is_ack = 1, acked_at = ? WHERE id = ?",
                (utc_now(), event_id),
            )
            if cursor.rowcount == 0:
                raise ApiError(404, "事件不存在")
        return {"ok": True, "events": self.list_events(acknowledged=False), "overview": self.overview()}

    def ack_all_events(self) -> dict[str, Any]:
        with self.connect() as conn:
            cursor = conn.execute(
                "UPDATE events SET is_ack = 1, acked_at = ? WHERE is_ack = 0",
                (utc_now(),),
            )
            count = cursor.rowcount
        return {
            "ok": True,
            "acked": count,
            "events": self.list_events(acknowledged=False),
            "overview": self.overview(),
        }

    def list_history(
        self,
        *,
        channel_id: int | None = None,
        kind: str | None = None,
        limit: int = 80,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if channel_id is not None:
            clauses.append("h.channel_id = ?")
            params.append(channel_id)
        if kind and kind != "all":
            clauses.append("h.kind = ?")
            params.append(kind)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        safe_limit = max(1, min(int(limit or 80), 300))
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT h.*, c.name AS channel_name, c.platform
                FROM history h
                LEFT JOIN channels c ON c.id = h.channel_id
                {where}
                ORDER BY h.created_at DESC, h.id DESC
                LIMIT ?
                """,
                (*params, safe_limit),
            ).fetchall()
        return [self.public_history(row) for row in rows]

    def list_history_by_channel(
        self,
        *,
        channel_ids: list[int],
        kind: str | None = None,
        limit_per_channel: int = 60,
    ) -> dict[int, list[dict[str, Any]]]:
        ids = list(dict.fromkeys(int(channel_id) for channel_id in channel_ids if channel_id is not None))
        if not ids:
            return {}
        safe_limit = max(1, min(int(limit_per_channel or 60), 300))
        placeholders = ",".join("?" for _ in ids)
        kind_clause = ""
        params: list[Any] = [*ids]
        if kind and kind != "all":
            kind_clause = "AND h.kind = ?"
            params.append(kind)
        params.append(safe_limit)
        with self.connect() as conn:
            rows = conn.execute(
                f"""
                WITH ranked_history AS (
                    SELECT
                        h.*,
                        c.name AS channel_name,
                        c.platform,
                        ROW_NUMBER() OVER (
                            PARTITION BY h.channel_id
                            ORDER BY h.created_at DESC, h.id DESC
                        ) AS history_rank
                    FROM history h
                    LEFT JOIN channels c ON c.id = h.channel_id
                    WHERE h.channel_id IN ({placeholders})
                      {kind_clause}
                )
                SELECT *
                FROM ranked_history
                WHERE history_rank <= ?
                ORDER BY channel_id, created_at DESC, id DESC
                """,
                params,
            ).fetchall()
        histories: dict[int, list[dict[str, Any]]] = {channel_id: [] for channel_id in ids}
        for row in rows:
            histories.setdefault(int(row["channel_id"]), []).append(self.public_history(row))
        return histories

    def public_history(self, row: Any) -> dict[str, Any]:
        return {
            "id": row["id"],
            "channel_id": row["channel_id"],
            "channelId": row["channel_id"],
            "channel_name": row["channel_name"],
            "channelName": row["channel_name"],
            "platform": row["platform"],
            "kind": row["kind"],
            "status": row["status"],
            "remaining": row["remaining"],
            "rate_multiplier": row["rate_multiplier"],
            "rateMultiplier": row["rate_multiplier"],
            "summary": history_payload_summary(row["kind"], row["payload_json"], row["remaining"], row["rate_multiplier"]),
            "created_at": row["created_at"],
            "createdAt": row["created_at"],
        }
