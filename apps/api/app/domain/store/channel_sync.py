from __future__ import annotations

import json
import sqlite3
from typing import Any

from apps.api.app.core.utils import bool_value, optional_float, utc_now
from apps.api.app.infrastructure.integrations import find_group, imported_key_matches_channel, normalize_key_provider

from .channel_constants import DEFAULT_MONITOR_MODELS


class ChannelSyncMixin:
    def is_sync_shell_channel(self, row: sqlite3.Row) -> bool:
        return (
            row["platform"] == "sub2Api"
            and not row["api_key"]
            and not row["external_key_id"]
            and bool(row["access_token"] or row["refresh_token"] or row["email"])
        )

    def upsert_synced_keys(
        self,
        parent_row: sqlite3.Row,
        keys: list[dict[str, Any]],
        groups: list[dict[str, Any]],
    ) -> list[int]:
        imported_ids: list[int] = []
        parent_id = int(parent_row["id"])
        parent_name = str(parent_row["name"] or "渠道")
        base_url = parent_row["base_url"]
        platform = parent_row["platform"]
        now = utc_now()
        with self.connect() as conn:
            for key in keys:
                external_key_id = str(key.get("external_key_id") or key.get("externalKeyId") or "").strip() or None
                api_key = str(key.get("api_key") or key.get("apiKey") or "").strip() or None
                masked_key = str(key.get("api_key_masked") or key.get("apiKeyMasked") or key.get("key_masked") or key.get("keyMasked") or "").strip() or None
                key_provider = normalize_key_provider(key.get("key_provider") or key.get("keyProvider") or key.get("provider") or key.get("type"))
                if not external_key_id and not api_key and not masked_key:
                    continue

                target_id: int | None = None
                if external_key_id:
                    existing = conn.execute(
                        """
                        SELECT id FROM channels
                        WHERE platform = ? AND base_url = ? AND external_key_id = ?
                        LIMIT 1
                        """,
                        (platform, base_url, external_key_id),
                    ).fetchone()
                    target_id = int(existing["id"]) if existing else None
                if target_id is None and not self.is_account_parent_row(parent_row) and imported_key_matches_channel(parent_row, key):
                    target_id = parent_id
                if target_id is None and api_key:
                    existing = conn.execute(
                        """
                        SELECT id FROM channels
                        WHERE platform = ? AND base_url = ? AND api_key = ?
                        LIMIT 1
                        """,
                        (platform, base_url, api_key),
                    ).fetchone()
                    target_id = int(existing["id"]) if existing else None

                key_group_id = key.get("group_id") or key.get("groupId") or parent_row["group_id"]
                selected = find_group(groups, key_group_id) or find_group(groups, parent_row["group_id"]) or (groups[0] if groups else None)
                group_id = (selected.get("group_id") if selected else key_group_id) or None
                group_name = (selected.get("group_name") if selected else key.get("group_name") or key.get("groupName") or group_id) or None
                if key_provider is None and selected:
                    key_provider = normalize_key_provider(
                        selected.get("platform")
                        or selected.get("provider")
                        or selected.get("provider_type")
                        or selected.get("providerType")
                        or selected.get("type")
                        or selected.get("group_name")
                        or selected.get("groupName")
                    )
                rate = optional_float(selected.get("rate_multiplier")) if selected else None
                key_name = str(key.get("key_name") or key.get("keyName") or "").strip() or None
                model_scope = str(key.get("model_scope") or key.get("modelScope") or parent_row["model_scope"] or "All models").strip()
                is_enabled = 1 if bool_value(key.get("is_enabled", key.get("isEnabled", True))) else 0
                monitor_models = self.monitor_models_for_provider(key_provider, key.get("monitor_models") or key.get("monitorModels"))
                monitor_models_json = json.dumps(monitor_models, ensure_ascii=False)
                default_monitor_models_json = json.dumps(DEFAULT_MONITOR_MODELS, ensure_ascii=False)

                if target_id is not None:
                    if target_id == parent_id:
                        channel_name = key_name or parent_name
                    else:
                        channel_name = key_name or f"{parent_name} #{external_key_id or target_id}"
                    source_channel_id = parent_row["source_channel_id"] if target_id == parent_id else parent_id
                    conn.execute(
                        """
                        UPDATE channels
                        SET name = ?,
                            model_scope = ?,
                            group_id = ?,
                            group_name = ?,
                            rate_multiplier = COALESCE(?, rate_multiplier),
                            api_key = COALESCE(?, api_key),
                            api_key_masked = COALESCE(?, api_key_masked),
                            access_token = COALESCE(?, access_token),
                            refresh_token = COALESCE(?, refresh_token),
                            user_id = COALESCE(?, user_id),
                            email = COALESCE(?, email),
                            password = COALESCE(?, password),
                            external_key_id = COALESCE(?, external_key_id),
                            key_name = COALESCE(?, key_name),
                            key_provider = COALESCE(?, key_provider),
                            source_channel_id = ?,
                            is_enabled = ?,
                            is_demo = 0,
                            is_account_parent = CASE WHEN id = ? THEN is_account_parent ELSE 0 END,
                            monitor_models = CASE
                                WHEN ? IS NULL THEN monitor_models
                                WHEN monitor_models IS NULL OR monitor_models = ? THEN ?
                                ELSE monitor_models
                            END,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            channel_name,
                            model_scope,
                            group_id,
                            group_name,
                            rate,
                            api_key,
                            masked_key,
                            parent_row["access_token"],
                            parent_row["refresh_token"],
                            parent_row["user_id"],
                            parent_row["email"],
                            parent_row["password"],
                            external_key_id,
                            key_name,
                            key_provider,
                            source_channel_id,
                            is_enabled,
                            parent_id,
                            key_provider,
                            default_monitor_models_json,
                            monitor_models_json,
                            now,
                            target_id,
                        ),
                    )
                else:
                    channel_name = key_name or f"{parent_name} #{external_key_id or len(imported_ids) + 1}"
                    cursor = conn.execute(
                        """
                        INSERT INTO channels (
                            name, platform, base_url, model_scope, group_id, group_name, rate_multiplier,
                            threshold, api_key, api_key_masked, access_token, refresh_token, user_id, email,
                            password, external_key_id, key_name, key_provider, source_channel_id, is_enabled, is_demo,
                            is_account_parent, is_default_key, monitor_models, disable_on_rate_multiplier_change,
                            disable_on_model_sync_failure, status, created_at, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, ?, ?, 'never', ?, ?)
                        """,
                        (
                            channel_name,
                            platform,
                            base_url,
                            model_scope,
                            group_id,
                            group_name,
                            rate,
                            optional_float(parent_row["threshold"]) or 10,
                            api_key,
                            masked_key,
                            parent_row["access_token"],
                            parent_row["refresh_token"],
                            parent_row["user_id"],
                            parent_row["email"],
                            parent_row["password"],
                            external_key_id,
                            key_name,
                            key_provider,
                            parent_id,
                            is_enabled,
                            monitor_models_json,
                            1 if parent_row["disable_on_rate_multiplier_change"] else 0,
                            1 if parent_row["disable_on_model_sync_failure"] else 0,
                            now,
                            now,
                        ),
                    )
                    target_id = int(cursor.lastrowid)
                if target_id not in imported_ids:
                    imported_ids.append(target_id)
            if imported_ids:
                placeholders = ", ".join("?" for _ in imported_ids)
                conn.execute(
                    f"""
                    DELETE FROM channels
                    WHERE source_channel_id = ?
                      AND id NOT IN ({placeholders})
                    """,
                    (parent_id, *imported_ids),
                )
            else:
                conn.execute(
                    """
                    DELETE FROM channels
                    WHERE source_channel_id = ?
                    """,
                    (parent_id,),
                )
            if imported_ids:
                existing_default = conn.execute(
                    """
                    SELECT id
                    FROM channels
                    WHERE (source_channel_id = ? OR id = ?)
                      AND is_default_key = 1
                    LIMIT 1
                    """,
                    (parent_id, parent_id),
                ).fetchone()
                if not existing_default:
                    conn.execute("UPDATE channels SET is_default_key = 1, updated_at = ? WHERE id = ?", (now, imported_ids[0]))
        return imported_ids
