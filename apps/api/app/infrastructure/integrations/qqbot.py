from __future__ import annotations

import hashlib
from typing import Any


ACCESS_TOKEN_ENDPOINT = "https://bots.qq.com/app/getAppAccessToken"
API_BASE_URL = "https://api.sgroup.qq.com"

TARGET_ENDPOINTS = {
    "group": "/v2/groups/{target_id}/messages",
    "user": "/v2/users/{target_id}/messages",
    "channel": "/channels/{target_id}/messages",
    "guild_dm": "/dms/{target_id}/messages",
}
TARGET_LABELS = {
    "subscribers": "自动订阅列表",
    "group": "QQ群",
    "user": "QQ单聊",
    "channel": "频道子频道",
    "guild_dm": "频道私信",
}

_P = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_I = pow(2, (_P - 1) // 4, _P)
_B = (
    15112221349535400772501151409588531511454012693041857206046113283949847762202,
    46316835694926478169428394003475163141307993866256225615783033603165251855960,
)


def bot_secret_seed(bot_secret: str) -> bytes:
    seed = str(bot_secret or "").encode("utf-8")
    if not seed:
        raise ValueError("QQBot Bot Secret 未配置")
    while len(seed) < 32:
        seed *= 2
    return seed[:32]


def sign_validation(bot_secret: str, event_ts: Any, plain_token: Any) -> str:
    message = f"{event_ts or ''}{plain_token or ''}".encode("utf-8")
    return _ed25519_sign(bot_secret_seed(bot_secret), message).hex()


def verify_callback(bot_secret: str, timestamp: str, body: bytes, signature_hex: str) -> bool:
    if not timestamp or not signature_hex:
        return False
    try:
        signature = bytes.fromhex(signature_hex)
    except ValueError:
        return False
    message = timestamp.encode("utf-8") + body
    try:
        public_key = _public_key_from_seed(bot_secret_seed(bot_secret))
        return _ed25519_verify(public_key, message, signature)
    except (ValueError, OverflowError):
        return False


def endpoint_for_target(target_type: str, target_id: str) -> str:
    template = TARGET_ENDPOINTS.get(target_type)
    if not template:
        raise ValueError("QQBot 通知目标类型不支持")
    return template.format(target_id=target_id)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P)
    x = pow(xx, (_P + 3) // 8, _P)
    if (x * x - xx) % _P != 0:
        x = (x * _I) % _P
    if x % 2 != 0:
        x = _P - x
    return x


def _is_on_curve(point: tuple[int, int]) -> bool:
    x, y = point
    return (-x * x + y * y - 1 - _D * x * x * y * y) % _P == 0


def _edwards_add(left: tuple[int, int], right: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = left
    x2, y2 = right
    denominator = pow(1 + _D * x1 * x2 * y1 * y2, _P - 2, _P)
    x3 = (x1 * y2 + x2 * y1) * denominator % _P
    denominator = pow(1 - _D * x1 * x2 * y1 * y2, _P - 2, _P)
    y3 = (y1 * y2 + x1 * x2) * denominator % _P
    return x3, y3


def _scalarmult(point: tuple[int, int], exponent: int) -> tuple[int, int]:
    if exponent == 0:
        return 0, 1
    partial = _scalarmult(point, exponent // 2)
    partial = _edwards_add(partial, partial)
    if exponent & 1:
        partial = _edwards_add(partial, point)
    return partial


def _encode_int(value: int) -> bytes:
    return int(value).to_bytes(32, "little")


def _encode_point(point: tuple[int, int]) -> bytes:
    x, y = point
    bits = bytearray(_encode_int(y))
    bits[31] |= (x & 1) << 7
    return bytes(bits)


def _decode_point(value: bytes) -> tuple[int, int]:
    if len(value) != 32:
        raise ValueError("Ed25519 point 必须是 32 字节")
    y = int.from_bytes(value, "little") & ((1 << 255) - 1)
    x = _xrecover(y)
    if bool(x & 1) != bool(value[31] >> 7):
        x = _P - x
    point = (x, y)
    if not _is_on_curve(point):
        raise ValueError("Ed25519 point 不在曲线上")
    return point


def _secret_scalar(seed: bytes) -> tuple[int, bytes]:
    digest = hashlib.sha512(seed).digest()
    scalar = int.from_bytes(digest[:32], "little")
    scalar &= (1 << 254) - 8
    scalar |= 1 << 254
    return scalar, digest[32:]


def _public_key_from_seed(seed: bytes) -> bytes:
    scalar, _ = _secret_scalar(seed)
    return _encode_point(_scalarmult(_B, scalar))


def _hint(value: bytes) -> int:
    return int.from_bytes(hashlib.sha512(value).digest(), "little")


def _ed25519_sign(seed: bytes, message: bytes) -> bytes:
    scalar, prefix = _secret_scalar(seed)
    public_key = _public_key_from_seed(seed)
    r = _hint(prefix + message) % _L
    encoded_r = _encode_point(_scalarmult(_B, r))
    h = _hint(encoded_r + public_key + message) % _L
    s = (r + h * scalar) % _L
    return encoded_r + _encode_int(s)


def _ed25519_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    if len(public_key) != 32 or len(signature) != 64:
        return False
    if signature[63] & 224:
        return False
    try:
        decoded_public = _decode_point(public_key)
        decoded_r = _decode_point(signature[:32])
    except ValueError:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _L:
        return False
    h = _hint(signature[:32] + public_key + message) % _L
    left = _scalarmult(_B, s)
    right = _edwards_add(decoded_r, _scalarmult(decoded_public, h))
    return _encode_point(left) == _encode_point(right)
