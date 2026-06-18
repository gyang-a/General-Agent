from __future__ import annotations
import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any

from .config import get_settings


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + padding).encode("utf-8"))


def _sign(payload_segment: str) -> str:
    settings = get_settings()
    digest = hmac.new(
        settings.auth_secret.encode("utf-8"),
        payload_segment.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _b64url_encode(digest)


def issue_auth_token(
    username: str,
    *,
    token_type: str = "access",
    ttl_ms: int | None = None,
    jti: str = "",
) -> str:
    settings = get_settings()
    now = int(time.time() * 1000)
    payload: dict[str, Any] = {
        "username": username,
        "type": token_type,
        "exp": now + (ttl_ms if ttl_ms is not None else settings.auth_token_ttl_ms),
        "iat": now,
    }
    if jti:
        payload["jti"] = jti

    payload_segment = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{payload_segment}.{_sign(payload_segment)}"


def issue_refresh_token(username: str) -> tuple[str, str]:
    settings = get_settings()
    jti = str(uuid.uuid4())
    token = issue_auth_token(
        username,
        token_type="refresh",
        ttl_ms=settings.refresh_token_ttl_ms,
        jti=jti,
    )
    return token, jti


def verify_auth_token(token: str, *, token_type: str = "") -> dict[str, Any]:
    if not token or "." not in token:
        return {"ok": False, "message": "Token 格式非法"}

    payload_segment, signature = token.split(".", 1)
    if not hmac.compare_digest(_sign(payload_segment), signature):
        return {"ok": False, "message": "Token 签名无效"}

    try:
        payload = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
    except Exception:
        return {"ok": False, "message": "Token 内容非法"}

    if int(payload.get("exp") or 0) <= int(time.time() * 1000):
        return {"ok": False, "message": "Token 已过期"}
    if not str(payload.get("username") or "").strip():
        return {"ok": False, "message": "Token 缺少用户名"}
    if token_type and payload.get("type") != token_type:
        return {"ok": False, "message": "Token 类型无效"}

    return {
        "ok": True,
        "username": str(payload.get("username")).strip(),
        "type": str(payload.get("type") or "access"),
        "jti": str(payload.get("jti") or "").strip(),
        "exp": int(payload.get("exp")),
    }

