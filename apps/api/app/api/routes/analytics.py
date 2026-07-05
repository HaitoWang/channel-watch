from __future__ import annotations

from typing import Optional

from apps.api.app.api.request import ApiRequest, RouteResult, ok


def handle(request: ApiRequest) -> Optional[RouteResult]:
    if request.method == "GET" and request.path == "/api/radar/overview":
        return ok({"overview": request.store.overview()})
    if request.method == "GET" and request.path == "/api/usage":
        return ok(request.store.usage_summary())
    if request.method == "GET" and request.path == "/api/rates":
        return ok(request.store.rate_summary())
    if request.method == "GET" and request.path == "/api/history":
        limit = request.int_query("limit", 80)
        kind = (request.query.get("kind") or [""])[0] or None
        channel_id = request.optional_int_query("channel_id", "channelId")
        return ok({"history": request.store.list_history(channel_id=channel_id, kind=kind, limit=limit)})
    return None
