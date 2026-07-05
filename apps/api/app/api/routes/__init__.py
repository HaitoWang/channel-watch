from __future__ import annotations

from apps.api.app.core.errors import ApiError

from apps.api.app.api.request import ApiRequest, RouteResult

from . import analytics, channels, events, monitoring, settings, system


ROUTERS = (
    system.handle,
    analytics.handle,
    channels.handle,
    events.handle,
    monitoring.handle,
    settings.handle,
)


def dispatch(request: ApiRequest) -> RouteResult:
    for route in ROUTERS:
        result = route(request)
        if result is not None:
            return result
    raise ApiError(404, "API 不存在")
