from __future__ import annotations

from apps.api.app.core.errors import ApiError

from apps.api.app.api.request import ApiRequest, RouteResult

from . import analytics, auth, channels, events, monitoring, settings, system


ROUTERS = (
    system.handle,
    analytics.handle,
    channels.handle,
    events.handle,
    monitoring.handle,
    settings.handle,
)

PUBLIC_ROUTES = {
    ("GET", "/api/health"),
    ("GET", "/api/auth/bootstrap"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/integrations/qqbot/webhook"),
}


def dispatch(request: ApiRequest) -> RouteResult:
    if request.path.startswith("/api/auth/"):
        result = auth.handle(request)
        if result is not None:
            return result

    if (request.method, request.path) not in PUBLIC_ROUTES:
        auth.require_auth(request)

    for route in ROUTERS:
        result = route(request)
        if result is not None:
            return result
    raise ApiError(404, "API 不存在")
