from __future__ import annotations

from fastapi import HTTPException, Response

from app.core.config import get_settings
from app.core.security import issue_auth_token, issue_refresh_token, verify_auth_token
from app.repositories import get_repository
from app.utils.time import now_ms


async def login(username: str, password: str, response: Response) -> dict:
    safe_username = username.strip()
    repo = get_repository()
    user = await repo.find_user_with_password(safe_username)
    if not user or str(user.get("password") or "") != password:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return await issue_login_payload(safe_username, response)


async def register(username: str, password: str, response: Response) -> dict:
    safe_username = username.strip()
    if not safe_username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    repo = get_repository()
    exists = await repo.find_user_with_password(safe_username)
    if exists:
        raise HTTPException(status_code=409, detail="用户名已存在")
    await repo.create_user(safe_username, password)
    return await issue_login_payload(safe_username, response)


async def issue_login_payload(username: str, response: Response) -> dict:
    settings = get_settings()
    repo = get_repository()
    access_token = issue_auth_token(username)
    refresh_token, jti = issue_refresh_token(username)
    now = now_ms()
    await repo.insert_refresh_token(
        {
            "jti": jti,
            "username": username,
            "createdAt": now,
            "expiresAt": now + settings.refresh_token_ttl_ms,
            "revokedAt": None,
            "revokedReason": "",
        }
    )
    response.set_cookie(
        settings.refresh_cookie_name,
        refresh_token,
        httponly=True,
        samesite="lax",
        max_age=settings.refresh_token_ttl_ms // 1000,
    )
    user = await repo.find_user_public(username)
    return {"ok": True, "token": access_token, "user": user or {"username": username, "avatarUrl": ""}}


async def me(username: str) -> dict:
    user = await get_repository().find_user_public(username)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"ok": True, "user": user}


async def logout(jti: str | None, response: Response) -> dict:
    settings = get_settings()
    if jti:
        await get_repository().revoke_refresh_token(jti, "logout")
    response.delete_cookie(settings.refresh_cookie_name)
    return {"ok": True}


async def refresh(refresh_token: str, response: Response) -> dict:
    settings = get_settings()
    verified = verify_auth_token(refresh_token, token_type="refresh")
    if not verified.get("ok"):
        response.delete_cookie(settings.refresh_cookie_name)
        return {"ok": False, "message": verified.get("message") or "登录已失效"}

    repo = get_repository()
    active = await repo.find_active_refresh_token(verified["jti"])
    if not active:
        response.delete_cookie(settings.refresh_cookie_name)
        return {"ok": False, "message": "登录已失效"}

    access_token = issue_auth_token(verified["username"])
    user = await repo.find_user_public(verified["username"])
    return {"ok": True, "token": access_token, "user": user}


async def update_avatar(username: str, avatar_url: str) -> dict:
    await get_repository().update_user_avatar(username, avatar_url)
    return {"ok": True, "avatarUrl": avatar_url, "username": username}
