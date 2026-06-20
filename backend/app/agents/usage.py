from __future__ import annotations

from typing import Any


def _get_field(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _get_path(value: Any, *path: str) -> Any:
    current = value
    for key in path:
        current = _get_field(current, key)
        if current is None:
            return None
    return current


def _token_count(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return max(0, int(value))
    if isinstance(value, str) and value.strip().isdigit():
        return max(0, int(value.strip()))
    return None


def _first_token_count(*values: Any) -> int | None:
    for value in values:
        count = _token_count(value)
        if count is not None:
            return count
    return None


def _normalize_token_usage(value: Any) -> dict[str, int] | None:
    usage = _get_field(value, "usage_metadata") or value
    response_usage = _get_path(value, "response_metadata", "token_usage") or _get_field(
        value,
        "token_usage",
    )

    input_tokens = _first_token_count(
        _get_field(usage, "input_tokens"),
        _get_field(usage, "prompt_tokens"),
        _get_field(response_usage, "input_tokens"),
        _get_field(response_usage, "prompt_tokens"),
    )
    output_tokens = _first_token_count(
        _get_field(usage, "output_tokens"),
        _get_field(usage, "completion_tokens"),
        _get_field(response_usage, "output_tokens"),
        _get_field(response_usage, "completion_tokens"),
    )
    total_tokens = _first_token_count(
        _get_field(usage, "total_tokens"),
        _get_field(response_usage, "total_tokens"),
    )
    cache_hit_tokens = _first_token_count(
        _get_path(usage, "input_token_details", "cache_read"),
        _get_path(usage, "input_token_details", "cached_tokens"),
        _get_path(usage, "prompt_tokens_details", "cached_tokens"),
        _get_path(response_usage, "input_token_details", "cache_read"),
        _get_path(response_usage, "input_token_details", "cached_tokens"),
        _get_path(response_usage, "prompt_tokens_details", "cached_tokens"),
    )

    if total_tokens is None and (input_tokens is not None or output_tokens is not None):
        total_tokens = (input_tokens or 0) + (output_tokens or 0)

    if all(item is None for item in (input_tokens, output_tokens, total_tokens, cache_hit_tokens)):
        return None

    return {
        "inputTokens": input_tokens or 0,
        "outputTokens": output_tokens or 0,
        "totalTokens": total_tokens or 0,
        "cacheHitTokens": cache_hit_tokens or 0,
    }


def extract_token_usage(value: Any) -> dict[str, int] | None:
    usage = _normalize_token_usage(value)
    if usage:
        return usage
    if isinstance(value, tuple):
        for item in value:
            usage = extract_token_usage(item)
            if usage:
                return usage
    if isinstance(value, dict):
        messages = value.get("messages")
        if isinstance(messages, list):
            for message in reversed(messages):
                usage = extract_token_usage(message)
                if usage:
                    return usage
    return _normalize_token_usage(_get_field(value, "message"))
