from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile

from app.core.config import get_settings
from app.core.security import verify_auth_token
from app.dependencies import require_auth
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services import auth_service
from app.services.upload_service import save_upload

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(payload: LoginRequest, response: Response) -> dict:
    return await auth_service.login(payload.username, payload.password, response)


@router.post("/register")
async def register(payload: RegisterRequest, response: Response) -> dict:
    return await auth_service.register(payload.username, payload.password, response)


@router.post("/refresh")
async def refresh(request: Request, response: Response) -> dict:
    settings = get_settings()
    token = request.cookies.get(settings.refresh_cookie_name) or ""
    return await auth_service.refresh(token, response)


@router.get("/me")
async def me(auth: dict = Depends(require_auth)) -> dict:
    return await auth_service.me(auth["username"])


@router.post("/logout")
async def logout(request: Request, response: Response) -> dict:
    settings = get_settings()
    token = request.cookies.get(settings.refresh_cookie_name) or ""
    verified = verify_auth_token(token, token_type="refresh")
    jti = verified.get("jti") if verified.get("ok") else None
    return await auth_service.logout(jti, response)


@router.post("/avatar")
async def avatar(avatar: UploadFile = File(...), auth: dict = Depends(require_auth)) -> dict:
    file = await save_upload(avatar)
    avatar_url = file["url"]
    return await auth_service.update_avatar(auth["username"], avatar_url)
