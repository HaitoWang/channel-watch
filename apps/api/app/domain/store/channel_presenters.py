from __future__ import annotations

import json
import sqlite3
from typing import Any

from apps.api.app.core.utils import mask_secret, optional_float
from apps.api.app.infrastructure.integrations import normalize_key_provider

from .channel_constants import DEFAULT_MONITOR_MODELS, PROVIDER_MONITOR_MODELS


class ChannelPresenterMixin:
    def public_channel(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        masked_key = data.get("api_key_masked")
        secret = data.get("api_key") or masked_key or data.get("access_token") or data.get("refresh_token")
        status = data.get("status") or "never"
        balance = optional_float(data.get("balance"))
        threshold = optional_float(data.get("threshold")) or 0
        quota_total = optional_float(data.get("quota_total"))
        if quota_total is not None and quota_total > 0 and balance is not None:
            remaining_percent = max(0, min(100, balance / quota_total * 100))
        elif balance is not None and threshold > 0:
            remaining_percent = max(0, min(100, balance / (threshold * 5) * 100))
        else:
            remaining_percent = 0 if status == "offline" else 35
        available_groups = self.list_channel_groups(data["id"])
        return {
            "id": data["id"],
            "name": data["name"],
            "platform": data["platform"],
            "base_url": data["base_url"],
            "baseUrl": data["base_url"],
            "model_scope": data.get("model_scope") or "All models",
            "modelScope": data.get("model_scope") or "All models",
            "group_id": data.get("group_id"),
            "groupId": data.get("group_id"),
            "group_name": data.get("group_name") or data.get("group_id") or "未选择分组",
            "groupName": data.get("group_name") or data.get("group_id") or "未选择分组",
            "rate_multiplier": data.get("rate_multiplier"),
            "rateMultiplier": data.get("rate_multiplier"),
            "external_key_id": data.get("external_key_id"),
            "externalKeyId": data.get("external_key_id"),
            "key_name": data.get("key_name"),
            "keyName": data.get("key_name"),
            "key_provider": data.get("key_provider"),
            "keyProvider": data.get("key_provider"),
            "api_key_masked": masked_key,
            "apiKeyMasked": masked_key,
            "source_channel_id": data.get("source_channel_id"),
            "sourceChannelId": data.get("source_channel_id"),
            "parent_name": data.get("parent_name"),
            "parentName": data.get("parent_name"),
            "threshold": threshold,
            "balance": balance,
            "unit": data.get("unit") or "USD",
            "quota_total": quota_total,
            "quotaTotal": quota_total,
            "used": data.get("used"),
            "status": status,
            "last_error": data.get("last_error"),
            "lastError": data.get("last_error"),
            "last_checked_at": data.get("last_checked_at"),
            "lastCheckedAt": data.get("last_checked_at"),
            "is_enabled": bool(data.get("is_enabled")),
            "isEnabled": bool(data.get("is_enabled")),
            "is_demo": bool(data.get("is_demo")),
            "isDemo": bool(data.get("is_demo")),
            "is_account_parent": bool(data.get("is_account_parent")),
            "isAccountParent": bool(data.get("is_account_parent")),
            "is_default_key": bool(data.get("is_default_key")),
            "isDefaultKey": bool(data.get("is_default_key")),
            "is_monitoring": bool(data.get("is_monitoring")),
            "isMonitoring": bool(data.get("is_monitoring")),
            "disable_on_rate_multiplier_change": bool(data.get("disable_on_rate_multiplier_change")),
            "disableOnRateMultiplierChange": bool(data.get("disable_on_rate_multiplier_change")),
            "disable_on_model_sync_failure": bool(data.get("disable_on_model_sync_failure")),
            "disableOnModelSyncFailure": bool(data.get("disable_on_model_sync_failure")),
            "scheduling_disabled_reason": data.get("scheduling_disabled_reason"),
            "schedulingDisabledReason": data.get("scheduling_disabled_reason"),
            "pool_account_ids": [item.strip() for item in str(data.get("pool_account_ids") or "").replace("，", ",").split(",") if item.strip()],
            "poolAccountIds": [item.strip() for item in str(data.get("pool_account_ids") or "").replace("，", ",").split(",") if item.strip()],
            "pool_rate_threshold": optional_float(data.get("pool_rate_threshold")),
            "poolRateThreshold": optional_float(data.get("pool_rate_threshold")),
            "pool_auto_schedule": bool(data.get("pool_auto_schedule")) if data.get("pool_auto_schedule") is not None else True,
            "poolAutoSchedule": bool(data.get("pool_auto_schedule")) if data.get("pool_auto_schedule") is not None else True,
            "pool_desired_state": data.get("pool_desired_state"),
            "poolDesiredState": data.get("pool_desired_state"),
            "pool_last_pushed_state": data.get("pool_last_pushed_state"),
            "poolLastPushedState": data.get("pool_last_pushed_state"),
            "pool_last_reason": data.get("pool_last_reason"),
            "poolLastReason": data.get("pool_last_reason"),
            "pool_last_error": data.get("pool_last_error"),
            "poolLastError": data.get("pool_last_error"),
            "pool_last_pushed_at": data.get("pool_last_pushed_at"),
            "poolLastPushedAt": data.get("pool_last_pushed_at"),
            "monitor_models": self.monitor_models_for_provider(data.get("key_provider"), data.get("monitor_models")),
            "monitorModels": self.monitor_models_for_provider(data.get("key_provider"), data.get("monitor_models")),
            "monitor_interval_seconds": int(data.get("monitor_interval_seconds") or 60),
            "monitorIntervalSeconds": int(data.get("monitor_interval_seconds") or 60),
            "monitor_status": data.get("monitor_status") or "idle",
            "monitorStatus": data.get("monitor_status") or "idle",
            "monitor_last_checked_at": data.get("monitor_last_checked_at"),
            "monitorLastCheckedAt": data.get("monitor_last_checked_at"),
            "monitor_last_error": data.get("monitor_last_error"),
            "monitorLastError": data.get("monitor_last_error"),
            "monitor_latency_ms": data.get("monitor_latency_ms"),
            "monitorLatencyMs": data.get("monitor_latency_ms"),
            "monitor_result": self.monitor_result(data.get("monitor_result_json")),
            "monitorResult": self.monitor_result(data.get("monitor_result_json")),
            "key_masked": masked_key or mask_secret(secret),
            "keyMasked": masked_key or mask_secret(secret),
            "has_api_key": bool(data.get("api_key")),
            "hasApiKey": bool(data.get("api_key")),
            "has_access_token": bool(data.get("access_token")),
            "hasAccessToken": bool(data.get("access_token")),
            "remaining_percent": round(remaining_percent, 2),
            "remainingPercent": round(remaining_percent, 2),
            "created_at": data.get("created_at"),
            "createdAt": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "updatedAt": data.get("updated_at"),
            "available_groups": available_groups,
            "availableGroups": available_groups,
        }

    def is_account_parent_row(self, row: sqlite3.Row) -> bool:
        return bool(row["is_account_parent"]) or self.is_sync_shell_channel(row)

    def monitor_models(self, value: Any) -> list[str]:
        if isinstance(value, list):
            models = value
        else:
            try:
                models = json.loads(value) if value else DEFAULT_MONITOR_MODELS
            except (TypeError, json.JSONDecodeError):
                models = str(value or "").split(",")
        result = [str(model).strip() for model in models if str(model).strip()]
        return result or DEFAULT_MONITOR_MODELS.copy()

    def monitor_models_for_provider(self, provider: Any, value: Any = None) -> list[str]:
        normalized_provider = normalize_key_provider(provider)
        models = self.monitor_models(value)
        if normalized_provider == "openai":
            filtered = [model for model in models if self.is_openai_monitor_model(model)]
            return filtered or PROVIDER_MONITOR_MODELS["openai"].copy()
        if normalized_provider == "anthropic":
            filtered = [model for model in models if self.is_anthropic_monitor_model(model)]
            return filtered or PROVIDER_MONITOR_MODELS["anthropic"].copy()
        return models

    def default_monitor_models(self, provider: Any) -> list[str]:
        normalized_provider = normalize_key_provider(provider)
        if normalized_provider in PROVIDER_MONITOR_MODELS:
            return PROVIDER_MONITOR_MODELS[normalized_provider].copy()
        return DEFAULT_MONITOR_MODELS.copy()

    def is_openai_monitor_model(self, model: Any) -> bool:
        return "gpt" in str(model or "").strip().lower()

    def is_anthropic_monitor_model(self, model: Any) -> bool:
        return "claude" in str(model or "").strip().lower()

    def monitor_result(self, value: Any) -> dict[str, Any] | None:
        if not value:
            return None
        try:
            payload = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None
