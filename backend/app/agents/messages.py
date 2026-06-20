from __future__ import annotations

from typing import Any


def message_type(chunk: Any) -> str:
    if chunk is None:
        return ""
    chunk_type = getattr(chunk, "type", "")
    if chunk_type:
        return str(chunk_type)
    if hasattr(chunk, "get_type"):
        return str(chunk.get_type())
    return str(getattr(getattr(chunk, "message", None), "type", "") or "")


def text_from_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "".join(text_from_value(item) for item in value)
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return value["text"]
        if isinstance(value.get("content"), str):
            return value["content"]
        if isinstance(value.get("content"), list):
            return "".join(text_from_value(item) for item in value["content"])
    return ""


def extract_chunk_text(chunk: Any) -> str:
    for value in (
        getattr(chunk, "content", None),
        getattr(chunk, "text", None),
        getattr(getattr(chunk, "message", None), "content", None),
    ):
        text = text_from_value(value)
        if text:
            return text
    return ""


def extract_final_text(result: Any) -> str:
    if isinstance(result, dict):
        messages = result.get("messages")
        if isinstance(messages, list):
            for message in reversed(messages):
                text = extract_chunk_text(message)
                if text:
                    return text
        for key in ("output", "content", "text"):
            text = text_from_value(result.get(key))
            if text:
                return text
    return extract_chunk_text(result) or text_from_value(result)
