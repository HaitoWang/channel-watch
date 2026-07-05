from __future__ import annotations

from typing import Optional

from apps.api.app.api.request import ApiRequest, RouteResult, ok
from apps.api.app.core.auth import (
    admin_user,
    create_access_token,
    credentials_summary,
    optional_auth,
    require_auth,
    verify_admin_password,
)
from apps.api.app.core.errors import ApiError


def handle(request: ApiRequest) -> Optional[RouteResult]:
    if request.method == "GET" and request.path == "/api/auth/bootstrap":
        user = optional_auth(request)
        return ok({**credentials_summary(), "authenticated": user is not None, "user": user})

    if request.method == "POST" and request.path == "/api/auth/login":
        payload = request.json()
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "")
        if not verify_admin_password(username, password):
            raise ApiError(401, "账号或密码不正确")
        access_token, expires_in = create_access_token(username)
        return ok(
            {
                "access_token": access_token,
                "expires_in": expires_in,
                "token_type": "Bearer",
                "user": admin_user(),
            }
        )

    if request.method == "GET" and request.path == "/api/auth/me":
        return ok({"user": require_auth(request)})

    if request.method == "POST" and request.path == "/api/auth/logout":
        return ok({"ok": True})

    return None
