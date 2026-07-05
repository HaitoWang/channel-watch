from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from apps.api.app.core.errors import ApiError
from apps.api.app.domain.store import RadarStore


JsonPayload = dict[str, Any]
RouteResult = tuple[JsonPayload, int]


@dataclass(frozen=True)
class ApiRequest:
    method: str
    path: str
    parts: list[str]
    query: dict[str, list[str]]
    store: RadarStore
    body: bytes
    headers: dict[str, str]

    def json(self) -> JsonPayload:
        raw = self.body
        if not raw:
            return {}
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ApiError(400, "请求 JSON 格式错误") from exc
        if not isinstance(payload, dict):
            raise ApiError(400, "请求体必须是 JSON 对象")
        return payload

    def raw_body(self) -> bytes:
        return self.body

    def header(self, name: str) -> str:
        target = name.lower()
        for key, value in self.headers.items():
            if key.lower() == target:
                return value
        return ""

    def int_query(self, name: str, default: int) -> int:
        value = (self.query.get(name) or [str(default)])[0] or str(default)
        try:
            return int(value)
        except ValueError as exc:
            raise ApiError(400, f"{name} 必须是数字") from exc

    def optional_int_query(self, *names: str) -> int | None:
        value = ""
        for name in names:
            value = (self.query.get(name) or [""])[0]
            if value:
                break
        if not value:
            return None
        try:
            return int(value)
        except ValueError as exc:
            raise ApiError(400, f"{names[0]} 必须是数字") from exc


def ok(payload: JsonPayload, status: int = 200) -> RouteResult:
    return payload, status


def channel_id_from(parts: list[str]) -> int:
    try:
        return int(parts[2])
    except (IndexError, ValueError) as exc:
        raise ApiError(400, "channel_id 必须是数字") from exc
