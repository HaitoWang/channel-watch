from __future__ import annotations

import base64
import json
import os
import socket
import ssl
import struct
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from apps.api.app.infrastructure.integrations.qqbot import API_BASE_URL as QQBOT_API_BASE_URL


GATEWAY_ENDPOINT = f"{QQBOT_API_BASE_URL}/gateway"
GROUP_AND_C2C_INTENT = 1 << 25
IDENTIFY_TIMEOUT_SECONDS = 30
RECONNECT_MIN_SECONDS = 3
RECONNECT_MAX_SECONDS = 60


def start_qqbot_gateway(store: Any) -> threading.Event:
    stop_event = threading.Event()
    thread = threading.Thread(target=QQBotGatewayRunner(store, stop_event).run, name="qqbot-gateway", daemon=True)
    thread.start()
    return stop_event


class QQBotGatewayRunner:
    def __init__(self, store: Any, stop_event: threading.Event) -> None:
        self.store = store
        self.stop_event = stop_event
        self.session_id = ""
        self.seq: int | None = None
        self.last_status = ""

    def run(self) -> None:
        backoff = RECONNECT_MIN_SECONDS
        while not self.stop_event.is_set():
            settings = self.store.notification_settings(include_secret=True)
            if not self.configured(settings):
                self.set_status("disabled")
                self.sleep(5)
                continue
            try:
                self.set_status("connecting")
                self.connect_once(settings)
                backoff = RECONNECT_MIN_SECONDS
            except Exception as exc:
                message = str(exc) or exc.__class__.__name__
                self.set_status("error", error=message, force=True)
                print(f"[qqbot-ws] {message}", flush=True)
                self.sleep(backoff)
                backoff = min(RECONNECT_MAX_SECONDS, backoff * 2)
        self.set_status("stopped", force=True)

    def configured(self, settings: dict[str, Any]) -> bool:
        app_id = str(settings.get("qqbot_app_id") or settings.get("qqbotAppId") or "").strip()
        secret = str(
            settings.get("qqbot_secret")
            or settings.get("qqbotSecret")
            or settings.get("qqbot_client_secret")
            or settings.get("qqbotClientSecret")
            or ""
        ).strip()
        return bool(app_id and secret)

    def set_status(self, status: str, *, error: str = "", force: bool = False) -> None:
        if force or status != self.last_status:
            self.store.update_qqbot_gateway_status(status, error=error)
            self.last_status = status

    def connect_once(self, settings: dict[str, Any]) -> None:
        access_token = self.store.qqbot_access_token(settings)
        gateway_url = self.gateway_url(access_token)
        ws = SimpleWebSocket.connect(gateway_url)
        try:
            hello = ws.recv_json(timeout=IDENTIFY_TIMEOUT_SECONDS)
            if hello.get("op") != 10:
                raise RuntimeError(f"QQBot Gateway 首包不是 Hello: {hello.get('op')}")
            interval_ms = int((hello.get("d") or {}).get("heartbeat_interval") or 45000)
            interval = max(5.0, interval_ms / 1000)
            self.identify(ws, access_token, settings)
            next_heartbeat = time.monotonic() + interval
            self.store.update_qqbot_gateway_status("connected", connected=True, session_id=self.session_id, seq=self.seq)
            self.last_status = "connected"
            while not self.stop_event.is_set():
                self.raise_if_config_changed(settings)
                timeout = max(0.5, next_heartbeat - time.monotonic())
                try:
                    payload = ws.recv_json(timeout=timeout)
                except TimeoutError:
                    self.heartbeat(ws)
                    next_heartbeat = time.monotonic() + interval
                    continue
                op = payload.get("op")
                if payload.get("s") is not None:
                    self.seq = int(payload["s"])
                    self.store.record_qqbot_gateway_sequence(self.seq)
                if op == 0:
                    self.handle_dispatch(payload)
                elif op == 1:
                    self.heartbeat(ws)
                    next_heartbeat = time.monotonic() + interval
                elif op == 7:
                    raise RuntimeError("QQBot Gateway 要求重连")
                elif op == 9:
                    self.session_id = ""
                    self.seq = None
                    raise RuntimeError("QQBot Gateway 会话失效")
                elif op == 10:
                    next_heartbeat = time.monotonic() + interval
                elif op == 11:
                    self.store.update_qqbot_gateway_status("connected", error="", session_id=self.session_id, seq=self.seq)
        finally:
            ws.close()

    def gateway_url(self, access_token: str) -> str:
        request = Request(GATEWAY_ENDPOINT, headers={"Accept": "application/json", "Authorization": f"QQBot {access_token}"}, method="GET")
        try:
            with urlopen(request, timeout=12) as response:
                body = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"QQBot Gateway HTTP {exc.code}: {detail or exc.reason}") from exc
        except URLError as exc:
            raise RuntimeError(f"QQBot Gateway 网络错误: {exc.reason}") from exc
        result = json.loads(body) if body else {}
        url = str(result.get("url") or "").strip()
        if not url:
            raise RuntimeError(f"QQBot Gateway 返回缺少 url: {body[:120]}")
        return url

    def identify(self, ws: "SimpleWebSocket", access_token: str, settings: dict[str, Any]) -> None:
        shard = [0, 1]
        seq = self.seq
        if seq is None:
            saved_seq = str(settings.get("qqbot_gateway_seq") or settings.get("qqbotGatewaySeq") or "").strip()
            if saved_seq:
                try:
                    seq = int(saved_seq)
                except ValueError:
                    seq = None
        session_id = self.session_id or str(settings.get("qqbot_gateway_session_id") or settings.get("qqbotGatewaySessionId") or "").strip()
        if session_id and seq is not None:
            ws.send_json({"op": 6, "d": {"token": f"QQBot {access_token}", "session_id": session_id, "seq": seq}})
            return
        ws.send_json(
            {
                "op": 2,
                "d": {
                    "token": f"QQBot {access_token}",
                    "intents": GROUP_AND_C2C_INTENT,
                    "shard": shard,
                    "properties": {"$os": os.uname().sysname, "$browser": "channel-watch", "$device": "channel-watch"},
                },
            }
        )

    def heartbeat(self, ws: "SimpleWebSocket") -> None:
        ws.send_json({"op": 1, "d": self.seq})

    def handle_dispatch(self, payload: dict[str, Any]) -> None:
        event_type = str(payload.get("t") or "")
        if event_type == "READY":
            data = payload.get("d") if isinstance(payload.get("d"), dict) else {}
            self.session_id = str(data.get("session_id") or data.get("sessionId") or self.session_id or "")
            self.store.update_qqbot_gateway_status("connected", error="", connected=True, session_id=self.session_id, seq=self.seq)
            return
        if event_type == "RESUMED":
            self.store.update_qqbot_gateway_status("connected", error="", connected=True, session_id=self.session_id, seq=self.seq)
            return
        self.store.record_qqbot_event(payload)

    def raise_if_config_changed(self, original: dict[str, Any]) -> None:
        current = self.store.notification_settings(include_secret=True)
        original_pair = (
            str(original.get("qqbot_app_id") or original.get("qqbotAppId") or ""),
            str(original.get("qqbot_secret") or original.get("qqbotSecret") or original.get("qqbot_client_secret") or original.get("qqbotClientSecret") or ""),
        )
        current_pair = (
            str(current.get("qqbot_app_id") or current.get("qqbotAppId") or ""),
            str(current.get("qqbot_secret") or current.get("qqbotSecret") or current.get("qqbot_client_secret") or current.get("qqbotClientSecret") or ""),
        )
        if original_pair != current_pair or not self.configured(current):
            raise RuntimeError("QQBot 配置已变化，准备重连")

    def sleep(self, seconds: int | float) -> None:
        self.stop_event.wait(seconds)


class SimpleWebSocket:
    def __init__(self, sock: ssl.SSLSocket | socket.socket) -> None:
        self.sock = sock

    @classmethod
    def connect(cls, url: str) -> "SimpleWebSocket":
        parsed = urlparse(url)
        if parsed.scheme not in {"ws", "wss"}:
            raise RuntimeError(f"QQBot Gateway URL 不支持: {parsed.scheme}")
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        raw = socket.create_connection((host, port), timeout=15)
        sock: ssl.SSLSocket | socket.socket
        if parsed.scheme == "wss":
            sock = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
        else:
            sock = raw
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = "\r\n".join(
            [
                f"GET {path} HTTP/1.1",
                f"Host: {host}:{port}",
                "Upgrade: websocket",
                "Connection: Upgrade",
                f"Sec-WebSocket-Key: {key}",
                "Sec-WebSocket-Version: 13",
                "User-Agent: channel-watch/qqbot-gateway",
                "\r\n",
            ]
        ).encode("ascii")
        sock.sendall(request)
        response = sock.makefile("rb", buffering=0)
        status = response.readline().decode("iso-8859-1", errors="replace").strip()
        headers: dict[str, str] = {}
        while True:
            line = response.readline().decode("iso-8859-1", errors="replace")
            if line in {"\r\n", "\n", ""}:
                break
            if ":" in line:
                name, value = line.split(":", 1)
                headers[name.strip().lower()] = value.strip()
        if not status.startswith("HTTP/1.1 101"):
            raise RuntimeError(f"QQBot Gateway 握手失败: {status}")
        return cls(sock)

    def recv_json(self, *, timeout: float) -> dict[str, Any]:
        message = self.recv_text(timeout=timeout)
        return json.loads(message)

    def recv_text(self, *, timeout: float) -> str:
        self.sock.settimeout(timeout)
        chunks: list[bytes] = []
        opcode = None
        while True:
            frame_opcode, data, final = self.read_frame()
            if frame_opcode == 8:
                raise RuntimeError("QQBot Gateway 已关闭连接")
            if frame_opcode == 9:
                self.send_frame(10, data)
                continue
            if frame_opcode == 10:
                continue
            if frame_opcode in {1, 2}:
                opcode = frame_opcode
                chunks.append(data)
            elif frame_opcode == 0 and opcode is not None:
                chunks.append(data)
            if final and chunks:
                payload = b"".join(chunks)
                return payload.decode("utf-8", errors="replace")

    def read_frame(self) -> tuple[int, bytes, bool]:
        head = self.read_exact(2)
        first, second = head[0], head[1]
        final = bool(first & 0x80)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self.read_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self.read_exact(8))[0]
        mask = self.read_exact(4) if masked else b""
        data = self.read_exact(length) if length else b""
        if masked:
            data = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        return opcode, data, final

    def read_exact(self, size: int) -> bytes:
        data = b""
        while len(data) < size:
            chunk = self.sock.recv(size - len(data))
            if not chunk:
                raise RuntimeError("QQBot Gateway 连接已断开")
            data += chunk
        return data

    def send_json(self, payload: dict[str, Any]) -> None:
        self.send_frame(1, json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    def send_frame(self, opcode: int, data: bytes = b"") -> None:
        length = len(data)
        header = bytearray([0x80 | opcode])
        if length < 126:
            header.append(0x80 | length)
        elif length <= 0xFFFF:
            header.extend(struct.pack("!BH", 0x80 | 126, length))
        else:
            header.extend(struct.pack("!BQ", 0x80 | 127, length))
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        self.sock.sendall(bytes(header) + mask + masked)

    def close(self) -> None:
        try:
            self.send_frame(8)
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass
