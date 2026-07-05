from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

from apps.api.app.core.config import ROOT
from apps.api.app.core.errors import ApiError
from apps.api.app.core.utils import utc_now


DEFAULT_USERNAME = "admin"
TOKEN_TTL_SECONDS = 12 * 60 * 60
PBKDF2_ITERATIONS = 210_000
AUTH_PATH = ROOT / "data" / "auth.json"
ADMIN_PASSWORD_PATH = ROOT / "data" / "admin-password.txt"


def ensure_admin_credentials() -> tuple[dict[str, Any], str | None]:
    if AUTH_PATH.exists():
        return _read_credentials(), None

    password = secrets.token_urlsafe(14)
    salt = secrets.token_bytes(16)
    credentials = {
        "username": DEFAULT_USERNAME,
        "password_salt": _b64_encode(salt),
        "password_hash": _hash_password(password, salt),
        "password_iterations": PBKDF2_ITERATIONS,
        "token_secret": secrets.token_urlsafe(48),
        "created_at": utc_now(),
    }
    AUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    _write_private_file(AUTH_PATH, json.dumps(credentials, ensure_ascii=False, indent=2).encode("utf-8"))
    _write_private_file(
        ADMIN_PASSWORD_PATH,
        (
            "Channel Radar admin login\n"
            f"username: {DEFAULT_USERNAME}\n"
            f"password: {password}\n"
            f"created_at: {credentials['created_at']}\n"
        ).encode("utf-8"),
    )
    return credentials, password


def verify_admin_password(username: str, password: str) -> bool:
    credentials, _ = ensure_admin_credentials()
    if username.strip() != credentials.get("username", DEFAULT_USERNAME):
        return False
    salt = _b64_decode(str(credentials.get("password_salt", "")))
    expected = str(credentials.get("password_hash", ""))
    actual = _hash_password(password, salt)
    return bool(expected) and hmac.compare_digest(expected, actual)


def create_access_token(username: str = DEFAULT_USERNAME) -> tuple[str, int]:
    credentials, _ = ensure_admin_credentials()
    now = int(time.time())
    payload = {
        "sub": username,
        "role": "admin",
        "iat": now,
        "exp": now + TOKEN_TTL_SECONDS,
    }
    payload_part = _b64_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _sign(payload_part, str(credentials["token_secret"]))
    return f"{payload_part}.{signature}", TOKEN_TTL_SECONDS


def require_auth(request: Any) -> dict[str, str]:
    token = _bearer_token(request.header("Authorization"))
    if not token:
        raise ApiError(401, "请先登录")
    user = user_from_token(token)
    if user is None:
        raise ApiError(401, "登录已过期，请重新登录")
    return user


def optional_auth(request: Any) -> dict[str, str] | None:
    token = _bearer_token(request.header("Authorization"))
    if not token:
        return None
    return user_from_token(token)


def user_from_token(token: str) -> dict[str, str] | None:
    credentials, _ = ensure_admin_credentials()
    try:
        payload_part, signature = token.split(".", 1)
    except ValueError:
        return None
    expected = _sign(payload_part, str(credentials["token_secret"]))
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        payload = json.loads(_b64_decode(payload_part).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("sub") != credentials.get("username", DEFAULT_USERNAME):
        return None
    if int(payload.get("exp") or 0) <= int(time.time()):
        return None
    return admin_user()


def admin_user() -> dict[str, str]:
    return {
        "username": DEFAULT_USERNAME,
        "display_name": "Admin",
        "role": "admin",
    }


def credentials_summary() -> dict[str, Any]:
    credentials, _ = ensure_admin_credentials()
    return {
        "username": credentials.get("username", DEFAULT_USERNAME),
        "password_file": str(ADMIN_PASSWORD_PATH),
        "created_at": credentials.get("created_at"),
    }


def _read_credentials() -> dict[str, Any]:
    try:
        payload = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ApiError(500, f"管理员凭据读取失败: {exc}") from exc
    if not isinstance(payload, dict):
        raise ApiError(500, "管理员凭据格式错误")
    return payload


def _hash_password(password: str, salt: bytes) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return _b64_encode(digest)


def _sign(payload_part: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload_part.encode("utf-8"), hashlib.sha256).digest()
    return _b64_encode(digest)


def _bearer_token(value: str) -> str:
    prefix = "Bearer "
    if not value or not value.lower().startswith(prefix.lower()):
        return ""
    return value[len(prefix) :].strip()


def _b64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def _write_private_file(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
