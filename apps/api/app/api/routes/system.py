from __future__ import annotations

from typing import Optional

from apps.api.app.api.request import ApiRequest, RouteResult, ok
from apps.api.app.core.utils import utc_now


def handle(request: ApiRequest) -> Optional[RouteResult]:
    if request.method == "GET" and request.path == "/api/health":
        return ok({"ok": True, "time": utc_now()})
    return None
