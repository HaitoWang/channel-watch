from __future__ import annotations

from .notification_config import NotificationConfigMixin
from .notification_content import NotificationContentMixin
from .notification_delivery import NotificationDeliveryMixin
from .notification_qqbot import NotificationQqbotMixin
from .notification_summary import NotificationSummaryMixin
from .sub2api_config import Sub2apiConfigMixin


class NotificationSettingsMixin(
    NotificationConfigMixin,
    Sub2apiConfigMixin,
    NotificationSummaryMixin,
    NotificationDeliveryMixin,
    NotificationQqbotMixin,
    NotificationContentMixin,
):
    """Combines notification settings, delivery, QQBot, and message formatting behavior."""

    def app_settings(self, *, include_secret: bool = False) -> dict:
        notification = self.notification_settings(include_secret=include_secret)
        sub2api = self.sub2api_settings(include_secret=include_secret)
        updated_at = max(
            notification.get("updated_at") or "",
            notification.get("updatedAt") or "",
            sub2api.get("sub2api_updated_at") or "",
            sub2api.get("sub2apiUpdatedAt") or "",
        ) or None
        return {
            **notification,
            **sub2api,
            "updated_at": updated_at,
            "updatedAt": updated_at,
        }

    def update_app_settings(self, payload: dict) -> dict:
        self.update_notification_settings(payload)
        self.update_sub2api_settings(payload)
        return {"ok": True, "settings": self.app_settings()}
