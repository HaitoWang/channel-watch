from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from apps.api.app.core.errors import ApiError
from apps.api.app.core.utils import mask_secret

from .notification_constants import (
    PUSHPLUS_ENDPOINT,
    QQBOT_ACCESS_TOKEN_ENDPOINT,
    QQBOT_API_BASE_URL,
    QQBOT_TARGET_ENDPOINTS,
    QQBOT_TARGET_LABELS,
    SERVERCHAN_ENDPOINT_TEMPLATE,
    endpoint_for_target,
)


class NotificationDeliveryMixin:
    def send_pushplus(self, settings: dict[str, Any], title: str, content: str) -> None:
        payload = {
            "token": settings.get("pushplus_token"),
            "title": title,
            "content": content,
            "template": settings.get("pushplus_template") or "markdown",
            "channel": settings.get("pushplus_channel") or "wechat",
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            PUSHPLUS_ENDPOINT,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=12) as response:
                body = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ApiError(502, f"pushplus HTTP {exc.code}: {detail or exc.reason}") from exc
        except URLError as exc:
            raise ApiError(502, f"pushplus 网络错误: {exc.reason}") from exc

        try:
            result = json.loads(body) if body else {}
        except json.JSONDecodeError as exc:
            raise ApiError(502, f"pushplus 返回无法解析: {body[:120]}") from exc
        code = result.get("code")
        if code not in {None, 0, 200}:
            message = result.get("msg") or result.get("message") or "未知错误"
            raise ApiError(502, f"pushplus 推送失败: {message}")

    def send_serverchan(self, settings: dict[str, Any], title: str, content: str) -> None:
        send_key = str(settings.get("serverchan_send_key") or "").strip()
        if not send_key:
            raise ApiError(400, "Server酱 SendKey 未配置")
        data = urlencode({"title": title, "desp": content, "short": self.notification_short(content)}).encode("utf-8")
        request = Request(
            SERVERCHAN_ENDPOINT_TEMPLATE.format(send_key=send_key),
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=12) as response:
                body = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ApiError(502, f"Server酱 HTTP {exc.code}: {detail or exc.reason}") from exc
        except URLError as exc:
            raise ApiError(502, f"Server酱网络错误: {exc.reason}") from exc

        try:
            result = json.loads(body) if body else {}
        except json.JSONDecodeError as exc:
            raise ApiError(502, f"Server酱返回无法解析: {body[:120]}") from exc
        code = result.get("code")
        errno = result.get("errno")
        if code not in {None, 0, 200} or (errno is not None and errno != 0):
            message = result.get("message") or result.get("msg") or result.get("errmsg") or "未知错误"
            raise ApiError(502, f"Server酱推送失败: {message}")

    def send_qqbot(self, settings: dict[str, Any], title: str, content: str) -> None:
        app_id = str(settings.get("qqbot_app_id") or settings.get("qqbotAppId") or "").strip()
        client_secret = str(
            settings.get("qqbot_secret")
            or settings.get("qqbotSecret")
            or settings.get("qqbot_client_secret")
            or settings.get("qqbotClientSecret")
            or ""
        ).strip()
        if not app_id:
            raise ApiError(400, "QQBot AppID 未配置")
        if not client_secret:
            raise ApiError(400, "QQBot Secret 未配置")
        targets = self.qqbot_delivery_targets(settings)
        access_token = self.qqbot_access_token(settings)

        message = f"{title}\n{content}".strip()
        if len(message) > 1800:
            message = f"{message[:1797]}..."
        payload = {"content": message, "msg_type": 0}
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        failures: list[str] = []
        for delivery_type, delivery_id in targets:
            try:
                self.send_qqbot_payload(delivery_type, delivery_id, data, access_token)
            except ApiError as exc:
                label = QQBOT_TARGET_LABELS.get(delivery_type, "QQBot")
                failures.append(f"{label} {mask_secret(delivery_id)}: {exc.message}")
        if failures:
            detail = "；".join(failures[:3])
            if len(failures) > 3:
                detail = f"{detail}；另有 {len(failures) - 3} 个目标失败"
            raise ApiError(502, f"QQBot 推送失败: {detail}")

    def send_qqbot_text(self, settings: dict[str, Any], target_type: str, target_id: str, content: str) -> None:
        message = str(content or "").strip()
        if len(message) > 1800:
            message = f"{message[:1797]}..."
        payload = {"content": message, "msg_type": 0}
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_qqbot_payload(target_type, target_id, data, self.qqbot_access_token(settings))

    def send_qqbot_payload(self, target_type: str, target_id: str, data: bytes, access_token: str) -> None:
        if target_type not in QQBOT_TARGET_ENDPOINTS:
            raise ApiError(400, "QQBot 通知目标类型不支持")
        if not target_id:
            raise ApiError(400, "QQBot 通知目标 ID 未配置")
        endpoint = endpoint_for_target(target_type, quote(target_id, safe=""))
        request = Request(
            f"{QQBOT_API_BASE_URL}{endpoint}",
            data=data,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                "Authorization": f"QQBot {access_token}",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=12) as response:
                body = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ApiError(502, f"QQBot HTTP {exc.code}: {detail or exc.reason}") from exc
        except URLError as exc:
            raise ApiError(502, f"QQBot 网络错误: {exc.reason}") from exc

        try:
            result = json.loads(body) if body else {}
        except json.JSONDecodeError as exc:
            raise ApiError(502, f"QQBot 返回无法解析: {body[:120]}") from exc
        code = result.get("code")
        if code not in {None, 0}:
            message_text = result.get("message") or result.get("msg") or result.get("errmsg") or "未知错误"
            raise ApiError(502, f"QQBot 推送失败: {message_text}")

    def qqbot_settings_configured(self, settings: dict[str, Any]) -> bool:
        app_id = str(settings.get("qqbot_app_id") or settings.get("qqbotAppId") or "").strip()
        secret = str(
            settings.get("qqbot_secret")
            or settings.get("qqbotSecret")
            or settings.get("qqbot_client_secret")
            or settings.get("qqbotClientSecret")
            or ""
        ).strip()
        target_type = str(settings.get("qqbot_target_type") or settings.get("qqbotTargetType") or "subscribers").strip().lower()
        target_id = str(settings.get("qqbot_target_id") or settings.get("qqbotTargetId") or "").strip()
        return bool(app_id and secret and (target_type == "subscribers" or target_id))

    def qqbot_delivery_targets(self, settings: dict[str, Any]) -> list[tuple[str, str]]:
        target_type = str(settings.get("qqbot_target_type") or settings.get("qqbotTargetType") or "subscribers").strip().lower()
        target_id = str(settings.get("qqbot_target_id") or settings.get("qqbotTargetId") or "").strip()
        if target_type == "subscribers":
            targets = [(item["target_type"], item["target_id"]) for item in self.list_qqbot_subscribers()]
            if not targets:
                raise ApiError(400, "暂无 QQBot 订阅对象，请先给机器人发送一条消息")
            return targets
        if target_type not in QQBOT_TARGET_ENDPOINTS:
            raise ApiError(400, "QQBot 通知目标类型不支持")
        if not target_id:
            raise ApiError(400, "QQBot 通知目标 ID 未配置")
        return [(target_type, target_id)]

    def qqbot_access_token(self, settings: dict[str, Any]) -> str:
        now = int(time.time())
        token = str(settings.get("qqbot_access_token") or settings.get("qqbotAccessToken") or "").strip()
        expires_at = self.qqbot_int(settings.get("qqbot_access_token_expires_at") or settings.get("qqbotAccessTokenExpiresAt"))
        if token and expires_at - now > 60:
            return token

        app_id = str(settings.get("qqbot_app_id") or settings.get("qqbotAppId") or "").strip()
        client_secret = str(
            settings.get("qqbot_secret")
            or settings.get("qqbotSecret")
            or settings.get("qqbot_client_secret")
            or settings.get("qqbotClientSecret")
            or ""
        ).strip()
        data = json.dumps({"appId": app_id, "clientSecret": client_secret}, ensure_ascii=False).encode("utf-8")
        request = Request(
            QQBOT_ACCESS_TOKEN_ENDPOINT,
            data=data,
            headers={"Content-Type": "application/json; charset=utf-8", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=12) as response:
                body = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ApiError(502, f"QQBot token HTTP {exc.code}: {detail or exc.reason}") from exc
        except URLError as exc:
            raise ApiError(502, f"QQBot token 网络错误: {exc.reason}") from exc

        try:
            result = json.loads(body) if body else {}
        except json.JSONDecodeError as exc:
            raise ApiError(502, f"QQBot token 返回无法解析: {body[:120]}") from exc
        code = result.get("code")
        if code not in {None, 0}:
            message = result.get("message") or result.get("msg") or result.get("errmsg") or "未知错误"
            raise ApiError(502, f"QQBot token 获取失败: {message}")
        token = str(result.get("access_token") or "").strip()
        if not token:
            raise ApiError(502, "QQBot token 返回缺少 access_token")
        expires_in = max(60, self.qqbot_int(result.get("expires_in"), default=7200))
        expires_at = now + expires_in
        settings["qqbot_access_token"] = token
        settings["qqbotAccessToken"] = token
        settings["qqbot_access_token_expires_at"] = str(expires_at)
        settings["qqbotAccessTokenExpiresAt"] = str(expires_at)
        self.save_app_settings({"qqbot_access_token": token, "qqbot_access_token_expires_at": str(expires_at)})
        return token

    def qqbot_int(self, value: Any, *, default: int = 0) -> int:
        if value is None or value == "":
            return default
        try:
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            return default
