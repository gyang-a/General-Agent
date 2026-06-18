from __future__ import annotations

import re
import uuid
from typing import Any

from app.db.mongo import get_db
from app.utils.time import now_ms


def _strip_id(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if doc is None:
        return None
    doc.pop("_id", None)
    return doc


def _message_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4()}"


def _title_from_message(message: str) -> str:
    compact = " ".join(str(message or "").strip().split())
    return compact[:18] or "新对话"


class MongoRepository:
    async def find_user_public(self, username: str) -> dict[str, Any] | None:
        doc = await get_db().users.find_one({"username": username}, {"_id": 0, "password": 0})
        return doc

    async def find_user_with_password(self, username: str) -> dict[str, Any] | None:
        return _strip_id(await get_db().users.find_one({"username": username}))

    async def create_user(self, username: str, password: str) -> None:
        await get_db().users.insert_one(
            {
                "username": username,
                "password": password,
                "avatarUrl": "",
                "customModels": [],
                "customEmbeddingModels": [],
                "embeddingModelSource": "auto",
                "createdAt": now_ms(),
            }
        )

    async def update_user_avatar(self, username: str, avatar_url: str) -> None:
        await get_db().users.update_one({"username": username}, {"$set": {"avatarUrl": avatar_url}})

    async def insert_refresh_token(self, payload: dict[str, Any]) -> None:
        await get_db().refresh_tokens.insert_one(payload)

    async def find_active_refresh_token(self, jti: str) -> dict[str, Any] | None:
        return _strip_id(await get_db().refresh_tokens.find_one({"jti": jti, "revokedAt": None}))

    async def revoke_refresh_token(self, jti: str, reason: str) -> None:
        await get_db().refresh_tokens.update_one(
            {"jti": jti},
            {"$set": {"revokedAt": now_ms(), "revokedReason": reason}},
        )

    async def load_history_snapshot(self, username: str) -> dict[str, Any]:
        conversations = [
            _strip_id(item)
            async for item in get_db().conversations.find({"username": username}).sort("updatedAt", -1)
        ]
        messages_by_conversation: dict[str, list[dict[str, Any]]] = {}
        async for item in get_db().messages.find({"username": username}).sort("createdAt", 1):
            item = _strip_id(item) or {}
            key = str(item.get("conversationId") or "")
            messages_by_conversation.setdefault(key, []).append(item)

        return {
            "conversations": conversations,
            "currentConversationId": conversations[0]["conversationId"] if conversations else None,
            "messagesByConversation": messages_by_conversation,
        }

    async def clear_conversation_messages(self, username: str, conversation_id: str) -> None:
        now = now_ms()
        await get_db().messages.delete_many({"username": username, "conversationId": conversation_id})
        await get_db().conversations.update_one(
            {"username": username, "conversationId": conversation_id},
            {
                "$set": {
                    "updatedAt": now,
                    "lastPreview": "",
                    "refs": [],
                    "contextDocs": [],
                }
            },
        )
        await self._delete_checkpoints_by_thread_ids([self._thread_id(username, conversation_id)])

    async def delete_conversation(self, username: str, conversation_id: str) -> None:
        await get_db().conversations.delete_one({"username": username, "conversationId": conversation_id})
        await get_db().messages.delete_many({"username": username, "conversationId": conversation_id})
        await self._delete_checkpoints_by_thread_ids([self._thread_id(username, conversation_id)])

    async def update_conversation(self, username: str, conversation_id: str, patch: dict[str, Any]) -> None:
        allowed = {}
        if "title" in patch:
            allowed["title"] = str(patch.get("title") or "").strip() or "未命名对话"
        if "pinned" in patch:
            allowed["pinned"] = bool(patch.get("pinned"))
        if not allowed:
            return
        now = now_ms()
        allowed["updatedAt"] = now
        await get_db().conversations.update_one(
            {"username": username, "conversationId": conversation_id},
            {
                "$set": allowed,
                "$setOnInsert": {
                    "username": username,
                    "conversationId": conversation_id,
                    "id": conversation_id,
                    "createdAt": now,
                    "lastPreview": "",
                    "refs": [],
                    "contextDocs": [],
                },
            },
            upsert=True,
        )

    async def clear_user_history(self, username: str) -> None:
        await get_db().conversations.delete_many({"username": username})
        await get_db().messages.delete_many({"username": username})
        await self._delete_checkpoints_by_user(username)

    async def get_custom_models(self, username: str) -> list[dict[str, Any]]:
        user = await get_db().users.find_one({"username": username}, {"customModels": 1})
        return list(user.get("customModels") or []) if user else []

    async def set_custom_models(self, username: str, models: list[dict[str, Any]]) -> None:
        await get_db().users.update_one({"username": username}, {"$set": {"customModels": models}})

    async def persist_user_message(
        self,
        username: str,
        conversation_id: str,
        message: str,
        attachments: list[dict[str, Any]],
        model: str,
    ) -> None:
        now = now_ms()
        await get_db().conversations.update_one(
            {"username": username, "conversationId": conversation_id},
            {
                "$setOnInsert": {
                    "username": username,
                    "conversationId": conversation_id,
                    "id": conversation_id,
                    "title": _title_from_message(message),
                    "pinned": False,
                    "createdAt": now,
                    "refs": [],
                    "contextDocs": [],
                },
                "$set": {"updatedAt": now, "lastPreview": message},
            },
            upsert=True,
        )
        await get_db().messages.insert_one(
            {
                "id": _message_id("msg_u"),
                "username": username,
                "conversationId": conversation_id,
                "role": "user",
                "content": message,
                "attachments": attachments,
                "model": model,
                "createdAt": now,
                "refs": [],
                "contextDocs": [],
                "retrievalModeUsed": "",
                "feedback": "none",
            }
        )

    async def persist_assistant_message(
        self,
        username: str,
        conversation_id: str,
        content: str,
        refs: list[dict[str, Any]],
        context_docs: list[dict[str, Any]],
        retrieval_mode_used: str,
    ) -> None:
        now = now_ms()
        await get_db().messages.insert_one(
            {
                "id": _message_id("msg_ai"),
                "username": username,
                "conversationId": conversation_id,
                "role": "assistant",
                "content": content,
                "attachments": [],
                "createdAt": now,
                "refs": refs,
                "contextDocs": context_docs,
                "retrievalModeUsed": retrieval_mode_used,
                "feedback": "none",
            }
        )
        await get_db().conversations.update_one(
            {"username": username, "conversationId": conversation_id},
            {
                "$set": {
                    "updatedAt": now,
                    "lastPreview": content,
                    "refs": refs,
                    "contextDocs": context_docs,
                }
            },
            upsert=True,
        )

    @staticmethod
    def _thread_id(username: str, conversation_id: str) -> str:
        return f"{username}:{conversation_id}"

    async def _delete_checkpoints_by_thread_ids(self, thread_ids: list[str]) -> None:
        safe_thread_ids = [item for item in thread_ids if item]
        if not safe_thread_ids:
            return
        query = {"thread_id": {"$in": safe_thread_ids}}
        await get_db().langgraph_checkpoints.delete_many(query)
        await get_db().langgraph_checkpoint_writes.delete_many(query)

    async def _delete_checkpoints_by_user(self, username: str) -> None:
        safe_username = str(username or "").strip()
        if not safe_username:
            return
        query = {"thread_id": {"$regex": f"^{re.escape(safe_username)}:"}}
        await get_db().langgraph_checkpoints.delete_many(query)
        await get_db().langgraph_checkpoint_writes.delete_many(query)
