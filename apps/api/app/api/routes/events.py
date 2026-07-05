from __future__ import annotations

from typing import Optional

from apps.api.app.api.request import ApiRequest, RouteResult, ok


def handle(request: ApiRequest) -> Optional[RouteResult]:
    if request.method == "GET" and request.path == "/api/events":
        ack_value = (request.query.get("ack") or request.query.get("status") or ["open"])[0].strip().lower()
        if ack_value in {"all", "*"}:
            acknowledged = None
        elif ack_value in {"ack", "acked", "true", "1", "yes"}:
            acknowledged = True
        else:
            acknowledged = False
        return ok({"events": request.store.list_events(acknowledged=acknowledged), "overview": request.store.overview()})

    if request.method == "POST" and request.path == "/api/events/ack-all":
        return ok(request.store.ack_all_events())

    if len(request.parts) == 4 and request.parts[1] == "events" and request.parts[3] == "ack" and request.method == "POST":
        return ok(request.store.ack_event(int(request.parts[2])))

    return None
