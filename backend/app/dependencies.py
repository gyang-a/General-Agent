from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from app.core.security import verify_auth_token
from app.repositories import get_repository


def resolve_bearer_token(request: Request) -> str:
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return ""
    return auth[7:].strip()


async def require_auth(request: Request) -> dict:
    token = resolve_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="未登录或登录已失效，请先登录")

    verified = verify_auth_token(token, token_type="access")
    if not verified.get("ok"):
        raise HTTPException(status_code=401, detail=verified.get("message") or "登录已失效，请重新登录")

    return {"username": verified["username"], "exp": verified["exp"]}


async def require_preview_auth(request: Request) -> dict:
    from app.core.config import get_settings

    settings = get_settings()
    token = request.cookies.get(settings.refresh_cookie_name) or ""
    verified = verify_auth_token(token, token_type="refresh")
    if not verified.get("ok"):
        raise HTTPException(status_code=401, detail=verified.get("message") or "登录已失效，请重新登录")

    active = await get_repository().find_active_refresh_token(verified["jti"])
    if not active:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
    return {"username": verified["username"], "exp": verified["exp"]}
