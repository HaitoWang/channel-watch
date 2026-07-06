"""以子进程方式调用 playwright_login.py 完成浏览器登录。

主后端进程不直接 import playwright（重依赖、需独立事件循环），而是
用 subprocess 隔离运行登录脚本，通过 stdout 的 JSON 拿回 token。
这样即使未安装 playwright，主服务也不受影响，只是该兜底能力不可用。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

from apps.api.app.core.errors import ApiError

_SCRIPT = os.path.join(os.path.dirname(__file__), "playwright_login.py")


def playwright_available() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


def login_via_playwright(base_url: str, email: str, password: str, *, timeout: int = 75) -> dict[str, str | None]:
    """用无头浏览器登录，返回 {access_token, refresh_token, user_id}。失败抛 ApiError。"""
    if not (base_url and email and password):
        raise ApiError(400, "浏览器登录需要 base_url + 账号 + 密码")
    if not playwright_available():
        raise ApiError(
            500,
            "未安装 playwright，无法用浏览器绕过 Cloudflare 登录；请先执行 `python3 -m pip install playwright && python3 -m playwright install chromium`",
        )
    try:
        proc = subprocess.run(
            [sys.executable, _SCRIPT, base_url, email, password, "--timeout", str(timeout)],
            capture_output=True,
            text=True,
            timeout=timeout + 20,
        )
    except subprocess.TimeoutExpired as exc:
        raise ApiError(504, "浏览器登录超时") from exc

    out = (proc.stdout or "").strip()
    if not out:
        detail = (proc.stderr or "").strip().splitlines()[-1:] or ["无输出"]
        raise ApiError(502, f"浏览器登录失败: {detail[0]}")
    # stdout 最后一行是结果 JSON
    line = out.splitlines()[-1]
    try:
        result: dict[str, Any] = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ApiError(502, f"浏览器登录返回无法解析: {line[:120]}") from exc
    if not result.get("ok") or not result.get("access_token"):
        raise ApiError(502, str(result.get("error") or "浏览器登录未拿到 token"))
    return {
        "access_token": result.get("access_token"),
        "refresh_token": result.get("refresh_token") or None,
        "user_id": result.get("user_id") or None,
    }
