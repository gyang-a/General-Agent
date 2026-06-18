from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import require_auth
from app.services.history_service import (
    clear_conversation_messages,
    clear_user_history,
    delete_conversation,
    load_history_snapshot,
    update_conversation,
)

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
async def get_history(auth: dict = Depends(require_auth)) -> dict:
    return await load_history_snapshot(auth["username"])


@router.delete("")
async def delete_history(auth: dict = Depends(require_auth)) -> dict:
    return await clear_user_history(auth["username"])


@router.patch("/conversations/{conversation_id}")
async def patch_conversation(
    conversation_id: str,
    payload: dict[str, Any],
    auth: dict = Depends(require_auth),
) -> dict:
    safe_id = str(conversation_id or "").strip()
    if not safe_id:
        raise HTTPException(status_code=400, detail="conversationId is required")
    return await update_conversation(auth["username"], safe_id, payload or {})


@router.delete("/conversations/{conversation_id}")
async def delete_history_conversation(
    conversation_id: str,
    auth: dict = Depends(require_auth),
) -> dict:
    safe_id = str(conversation_id or "").strip()
    if not safe_id:
        raise HTTPException(status_code=400, detail="conversationId is required")
    return await delete_conversation(auth["username"], safe_id)


@router.delete("/conversations/{conversation_id}/messages")
async def delete_conversation_messages(
    conversation_id: str,
    auth: dict = Depends(require_auth),
) -> dict:
    safe_id = str(conversation_id or "").strip()
    if not safe_id:
        raise HTTPException(status_code=400, detail="conversationId is required")
    return await clear_conversation_messages(auth["username"], safe_id)
