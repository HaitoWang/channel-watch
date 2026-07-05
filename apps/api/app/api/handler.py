from __future__ import annotations

from http.server import BaseHTTPRequestHandler
from typing import Any
from urllib.parse import parse_qs, urlparse

from apps.api.app.core.config import DB_PATH
from apps.api.app.core.errors import ApiError
from apps.api.app.core.utils import json_dumps
from apps.api.app.domain.store import RadarStore

from .request import ApiRequest
from .routes import dispatch


class ApiHandler(BaseHTTPRequestHandler):
    store = RadarStore(DB_PATH)

    def do_GET(self) -> None:
        self.route()

    def do_POST(self) -> None:
        self.route()

    def do_PATCH(self) -> None:
        self.route()

    def do_DELETE(self) -> None:
        self.route()

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}", flush=True)

    def route(self) -> None:
        try:
            parsed = urlparse(self.path)
            if not parsed.path.startswith("/api/"):
                raise ApiError(404, "API 不存在")
            body = self.read_body()
            request = ApiRequest(
                method=self.command,
                path=parsed.path,
                parts=[part for part in parsed.path.split("/") if part],
                query=parse_qs(parsed.query),
                store=self.store,
                body=body,
                headers={key: value for key, value in self.headers.items()},
            )
            payload, status = dispatch(request)
            self.write_json(payload, status=status)
        except ApiError as exc:
            self.write_json({"ok": False, "message": exc.message}, status=exc.status)
        except Exception as exc:
            self.write_json({"ok": False, "message": f"服务异常: {exc}"}, status=500)

    def read_body(self) -> bytes:
        length = int(self.headers.get("content-length") or 0)
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def write_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json_dumps(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
