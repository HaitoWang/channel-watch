from __future__ import annotations

import sqlite3
from typing import Any

from apps.api.app.core.errors import ApiError
from apps.api.app.core.utils import normalize_base_url

from ._http import http_json, unwrap_data
from .parsers import find_nested_text


def sub2api_access_token(row: sqlite3.Row) -> str:
    if row["access_token"]:
        return str(row["access_token"])
    base_url = row["base_url"].rstrip("/")
    if row["refresh_token"]:
        auth = refresh_sub2api_session(base_url, row["refresh_token"])
        token = auth.get("access_token")
        if token:
            return token
    if not row["email"] or not row["password"]:
        raise ApiError(400, "sub2Api 查组缺少 accessToken/refreshToken 或 email/password")
    auth = login_sub2api_credentials(base_url, row["email"], row["password"])
    token = auth.get("access_token")
    if not token:
        raise ApiError(502, "sub2Api 登录成功但没有 access_token")
    return token


def login_sub2api_credentials(
    base_url: str,
    email: str,
    password: str,
    turnstile_token: str | None = None,
) -> dict[str, str | None]:
    url = normalize_base_url(base_url)
    body = {"email": email, "password": password}
    if turnstile_token:
        body["turnstile_token"] = turnstile_token
    payload = http_json(
        "POST",
        f"{url}/api/v1/auth/login",
        {"Origin": url, "Referer": f"{url}/login"},
        body,
    )
    auth = extract_auth_tokens(payload)
    if not auth.get("access_token"):
        raise ApiError(502, "sub2Api 登录成功但没有返回 access_token")
    return auth


def refresh_sub2api_session(base_url: str, refresh_token: str) -> dict[str, str | None]:
    url = normalize_base_url(base_url)
    payload = http_json(
        "POST",
        f"{url}/api/v1/auth/refresh",
        {"Origin": url, "Referer": f"{url}/login"},
        {"refresh_token": refresh_token},
    )
    auth = extract_auth_tokens(payload)
    if not auth.get("access_token"):
        raise ApiError(502, "sub2Api 刷新成功但没有返回 access_token")
    return auth


def extract_auth_tokens(payload: Any) -> dict[str, str | None]:
    return {
        "access_token": find_nested_text(payload, "access_token", "accessToken", "token"),
        "refresh_token": find_nested_text(payload, "refresh_token", "refreshToken"),
        "user_id": find_nested_text(payload, "user_id", "userId", "id"),
    }


def extract_access_token(payload: Any) -> str | None:
    data = unwrap_data(payload)
    if isinstance(data, dict):
        return data.get("access_token") or data.get("accessToken") or data.get("token")
    if isinstance(payload, dict):
        return payload.get("access_token") or payload.get("accessToken") or payload.get("token")
    return None
