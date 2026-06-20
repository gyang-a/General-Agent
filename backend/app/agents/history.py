from __future__ import annotations

import json
from typing import Any


def _message_role(message: Any) -> str:
    return (
        str(getattr(message, "type", "") or "")
        or str(getattr(message, "role", "") or "")
        or message.__class__.__name__
    )


def _message_to_debug_dict(message: Any) -> dict[str, Any]:
    if hasattr(message, "model_dump"):
        dumped = message.model_dump(mode="json")
        if isinstance(dumped, dict):
            return dumped

    if hasattr(message, "dict"):
        dumped = message.dict()
        if isinstance(dumped, dict):
            return dumped

    return {
        "type": _message_role(message),
        "repr": repr(message),
        "content": getattr(message, "content", None),
        "tool_calls": getattr(message, "tool_calls", None),
        "additional_kwargs": getattr(message, "additional_kwargs", None),
        "response_metadata": getattr(message, "response_metadata", None),
        "usage_metadata": getattr(message, "usage_metadata", None),
    }


def print_message_object(message: Any, *, prefix: str = "[agent message]") -> None:
    payload = _message_to_debug_dict(message)
    print(f"{prefix} {_message_role(message)} {message.__class__.__name__}")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


async def print_agent_history(agent: Any, run_config: dict[str, Any]) -> None:
    if hasattr(agent, "aget_state"):
        snapshot = await agent.aget_state(run_config)
    else:
        snapshot = agent.get_state(run_config)

    values = getattr(snapshot, "values", {}) or {}
    messages = values.get("messages", [])

    print(f"[agent history] {len(messages)} messages")
    for index, message in enumerate(messages, start=1):
        print_message_object(message, prefix=f"[agent history] {index}.")
