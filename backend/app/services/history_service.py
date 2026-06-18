from __future__ import annotations

from typing import Any

from app.repositories import get_repository


async def load_history_snapshot(username: str) -> dict[str, Any]:
    return {"ok": True, **await get_repository().load_history_snapshot(username)}


async def clear_conversation_messages(username: str, conversation_id: str) -> dict[str, Any]:
    await get_repository().clear_conversation_messages(username, conversation_id)
    return {"ok": True}


async def delete_conversation(username: str, conversation_id: str) -> dict[str, Any]:
    await get_repository().delete_conversation(username, conversation_id)
    return {"ok": True}


async def update_conversation(username: str, conversation_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    await get_repository().update_conversation(username, conversation_id, patch)
    return {"ok": True}


async def clear_user_history(username: str) -> dict[str, Any]:
    await get_repository().clear_user_history(username)
    return {"ok": True}
