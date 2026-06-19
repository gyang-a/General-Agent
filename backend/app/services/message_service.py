from __future__ import annotations

from typing import Any

from app.repositories import get_repository


async def persist_user_message(
    username: str,
    conversation_id: str,
    message: str,
    attachments: list[dict[str, Any]],
    model: str,
) -> None:
    await get_repository().persist_user_message(username, conversation_id, message, attachments, model)


async def persist_assistant_message(
    username: str,
    conversation_id: str,
    content: str,
    refs: list[dict[str, Any]],
    context_docs: list[dict[str, Any]],
    retrieval_mode_used: str,
    usage: dict[str, Any] | None = None,
) -> None:
    await get_repository().persist_assistant_message(
        username,
        conversation_id,
        content,
        refs,
        context_docs,
        retrieval_mode_used,
        usage,
    )
