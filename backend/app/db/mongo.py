from __future__ import annotations

import time
from typing import Any
from collections.abc import Callable

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.checkpoints import create_checkpointer
from app.checkpoints.state import set_active_checkpointer
from app.core.config import Settings


class Mongo:
    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None
    checkpointer: Any = None
    close_checkpointer: Callable[[], None] | None = None


mongo = Mongo()


async def connect_mongo(settings: Settings) -> None:
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]

    await db.users.create_index("username", unique=True)
    await db.conversations.create_index([("username", 1), ("conversationId", 1)], unique=True)
    await db.conversations.create_index([("username", 1), ("updatedAt", -1)])
    await db.messages.create_index([("username", 1), ("conversationId", 1), ("createdAt", 1)])
    await db.refresh_tokens.create_index("jti", unique=True)
    await db.refresh_tokens.create_index([("username", 1), ("createdAt", -1)])
    await db.refresh_tokens.create_index("expiresAt", expireAfterSeconds=0)
    await db.langgraph_checkpoints.create_index(
        [("thread_id", 1), ("checkpoint_ns", 1), ("checkpoint_id", -1)],
        unique=True,
    )
    await db.langgraph_checkpoint_writes.create_index(
        [("thread_id", 1), ("checkpoint_ns", 1), ("checkpoint_id", 1), ("task_id", 1), ("idx", 1)],
        unique=True,
    )

    await db.users.update_one(
        {"username": settings.auth_username},
        {
            "$setOnInsert": {
                "username": settings.auth_username,
                "password": settings.auth_password,
                "avatarUrl": "",
                "customModels": [],
                "customEmbeddingModels": [],
                "embeddingModelSource": "auto",
                "createdAt": int(time.time() * 1000),
            }
        },
        upsert=True,
    )

    mongo.client = client
    mongo.db = db
    mongo.checkpointer, mongo.close_checkpointer = create_checkpointer(settings)
    set_active_checkpointer(mongo.checkpointer)


async def close_mongo() -> None:
    if mongo.close_checkpointer:
        mongo.close_checkpointer()
    if mongo.client:
        mongo.client.close()
    mongo.client = None
    mongo.db = None
    mongo.checkpointer = None
    mongo.close_checkpointer = None
    set_active_checkpointer(None)


def get_db() -> AsyncIOMotorDatabase:
    if mongo.db is None:
        raise RuntimeError("MongoDB 未初始化")
    return mongo.db
