from __future__ import annotations

from typing import Optional

from apps.api.app.api.request import ApiRequest, RouteResult, channel_id_from, ok


def handle(request: ApiRequest) -> Optional[RouteResult]:
    if request.method == "GET" and request.path == "/api/monitor":
        return ok(request.store.monitor_summary())

    if (
        request.method == "POST"
        and len(request.parts) == 5
        and request.parts[1] == "channels"
        and request.parts[3] == "monitor"
        and request.parts[4] == "probe"
    ):
        return ok(request.store.probe_models(channel_id_from(request.parts)))

    return None
