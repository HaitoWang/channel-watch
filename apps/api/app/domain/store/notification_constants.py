from __future__ import annotations

from apps.api.app.infrastructure.integrations.qqbot import (
    ACCESS_TOKEN_ENDPOINT as QQBOT_ACCESS_TOKEN_ENDPOINT,
    API_BASE_URL as QQBOT_API_BASE_URL,
    TARGET_ENDPOINTS as QQBOT_TARGET_ENDPOINTS,
    TARGET_LABELS as QQBOT_TARGET_LABELS,
    endpoint_for_target,
    sign_validation,
    verify_callback,
)


PUSHPLUS_ENDPOINT = "https://www.pushplus.plus/send"
SERVERCHAN_ENDPOINT_TEMPLATE = "https://sctapi.ftqq.com/{send_key}.send"
NOTIFICATION_CHANNELS = {"pushplus", "serverchan", "qqbot"}
PUSHPLUS_CHANNELS = {"wechat", "webhook", "cp", "mail", "sms", "call", "app"}
PUSHPLUS_TEMPLATES = {"markdown", "html", "txt", "json"}
QQBOT_TARGET_TYPES = set(QQBOT_TARGET_ENDPOINTS) | {"subscribers"}
MONITOR_SUMMARY_EVENT_TYPES = {"low_balance", "rate_changed", "model_probe_failed", "probe_failed"}
MONITOR_SUMMARY_MAX_ITEMS = 6
