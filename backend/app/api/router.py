from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import auth, chat, health, history, kb, models, upload

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(models.router)
api_router.include_router(history.router)
api_router.include_router(kb.router)
api_router.include_router(upload.router)
api_router.include_router(chat.router)

