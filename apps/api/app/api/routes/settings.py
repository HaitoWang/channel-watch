from __future__ import annotations

from typing import Optional

from apps.api.app.api.request import ApiRequest, RouteResult, ok


def handle(request: ApiRequest) -> Optional[RouteResult]:
    if request.method == "GET" and request.path == "/api/settings":
        return ok({"settings": request.store.app_settings()})
    if request.method == "PATCH" and request.path == "/api/settings":
        return ok(request.store.update_app_settings(request.json()))
    if request.method == "POST" and request.path == "/api/settings/test-pushplus":
        return ok(request.store.send_test_notification())
    if request.method == "POST" and request.path == "/api/settings/test-serverchan":
        return ok(request.store.send_test_serverchan_notification())
    if request.method == "POST" and request.path == "/api/settings/test-notification":
        return ok(request.store.send_test_active_notification(request.json()))
    if request.method == "POST" and request.path == "/api/integrations/qqbot/webhook":
        return ok(request.store.handle_qqbot_webhook(request.headers, request.raw_body()))
    return None
