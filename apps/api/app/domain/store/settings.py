from __future__ import annotations

from .notification_config import NotificationConfigMixin
from .notification_content import NotificationContentMixin
from .notification_delivery import NotificationDeliveryMixin
from .notification_qqbot import NotificationQqbotMixin
from .notification_summary import NotificationSummaryMixin


class NotificationSettingsMixin(
    NotificationConfigMixin,
    NotificationSummaryMixin,
    NotificationDeliveryMixin,
    NotificationQqbotMixin,
    NotificationContentMixin,
):
    """Combines notification settings, delivery, QQBot, and message formatting behavior."""
