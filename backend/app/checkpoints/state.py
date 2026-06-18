from __future__ import annotations

from typing import Any

_active_checkpointer: Any = None


def set_active_checkpointer(checkpointer: Any) -> None:
    global _active_checkpointer
    _active_checkpointer = checkpointer


def get_active_checkpointer() -> Any:
    return _active_checkpointer

