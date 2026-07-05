from __future__ import annotations

from .analytics import AnalyticsMixin
from .channels import ChannelRepositoryMixin
from .events import EventLogMixin
from .monitoring import MonitoringMixin
from .probes import ProbeServiceMixin
from .schema import SchemaMixin
from .settings import NotificationSettingsMixin


class RadarStore(
    SchemaMixin,
    ChannelRepositoryMixin,
    AnalyticsMixin,
    ProbeServiceMixin,
    MonitoringMixin,
    EventLogMixin,
    NotificationSettingsMixin,
):
    """Coordinates persistence and domain operations for Channel Radar."""


__all__ = ["RadarStore"]
