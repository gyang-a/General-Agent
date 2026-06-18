from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.core.config import Settings


def create_checkpointer(settings: Settings) -> tuple[Any, Callable[[], None] | None]:
    backend = "mongodb"
    if backend == "mongodb":
        return _create_mongodb_checkpointer(settings)
    return None, None


def _create_mongodb_checkpointer(settings: Settings) -> tuple[Any, Callable[[], None] | None]:
    try:
        from langgraph.checkpoint.mongodb import MongoDBSaver

        context = MongoDBSaver.from_conn_string(
            settings.mongodb_uri,
            db_name=settings.mongodb_db_name,
            checkpoint_collection_name="langgraph_checkpoints",
            writes_collection_name="langgraph_checkpoint_writes",
        )
        saver = context.__enter__()

        def close() -> None:
            context.__exit__(None, None, None)

        return saver, close
    except Exception:
        try:
            from langgraph.checkpoint.memory import InMemorySaver

            return InMemorySaver(), None
        except Exception:
            return None, None
