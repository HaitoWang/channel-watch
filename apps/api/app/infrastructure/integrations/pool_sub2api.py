"""我方 sub2api 号池的写动作封装。

监控系统（channel-watc）根据上游指标，调用我方 sub2api 的 admin 接口
开关号池账号（account）的调度状态：

    POST {base_url}/api/v1/admin/accounts/{account_id}/schedulable
    Header: x-api-key: <admin-api-key>
    Body:   {"schedulable": true|false}

复用项目内 urllib 封装 http_json，不引入第三方依赖。
"""

from __future__ import annotations

from typing import Any

from apps.api.app.core.errors import ApiError
from apps.api.app.core.utils import normalize_base_url

from ._http import http_json


def set_account_schedulable(
    base_url: str,
    admin_api_key: str,
    account_id: str | int,
    enabled: bool,
) -> Any:
    """开关我方号池账号调度。成功返回上游响应体，失败抛 ApiError。"""
    base = normalize_base_url(base_url)
    if not base:
        raise ApiError(400, "号池 Base URL 未配置")
    if not str(admin_api_key or "").strip():
        raise ApiError(400, "号池 Admin API Key 未配置")
    account = str(account_id).strip()
    if not account:
        raise ApiError(400, "缺少号池账号 ID")
    headers = {
        "x-api-key": str(admin_api_key).strip(),
        "Referer": f"{base}/accounts",
    }
    return http_json(
        "POST",
        f"{base}/api/v1/admin/accounts/{account}/schedulable",
        headers,
        {"schedulable": bool(enabled)},
    )
