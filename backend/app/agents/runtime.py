from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from pydantic import BaseModel, Field

from app.agents.registry import to_openai_client_base_url
from app.agents.tools import create_web_search_tool
from app.checkpoints.state import get_active_checkpointer
from app.core.config import get_settings


class AgentRunInput(BaseModel):
    username: str
    provider: dict[str, Any] = Field(default_factory=dict)
    model: str
    conversation_id: str
    message: str
    rag_context: str = ""
    use_web_search: bool = False
    refs: list[dict[str, Any]] = Field(default_factory=list)
    context_docs: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_mode_used: str = "none"


@dataclass
class AgentRunState:
    content: str = ""
    refs: list[dict[str, Any]] = field(default_factory=list)
    context_docs: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] | None = None
    error: str = ""
    aborted: bool = False


def _message_type(chunk: Any) -> str:
    if chunk is None:
        return ""
    get_type = getattr(chunk, "type", "")
    if get_type:
        return str(get_type)
    if hasattr(chunk, "get_type"):
        return str(chunk.get_type())
    return str(getattr(getattr(chunk, "message", None), "type", "") or "")


def _text_from_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "".join(_text_from_value(item) for item in value)
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return value["text"]
        if isinstance(value.get("content"), str):
            return value["content"]
        if isinstance(value.get("content"), list):
            return "".join(_text_from_value(item) for item in value["content"])
    return ""


def _extract_chunk_text(chunk: Any) -> str:
    for value in (
        getattr(chunk, "content", None),
        getattr(chunk, "text", None),
        getattr(getattr(chunk, "message", None), "content", None),
    ):
        text = _text_from_value(value)
        if text:
            return text
    return ""


def _extract_final_text(result: Any) -> str:
    if isinstance(result, dict):
        messages = result.get("messages")
        if isinstance(messages, list):
            for message in reversed(messages):
                text = _extract_chunk_text(message)
                if text:
                    return text
        for key in ("output", "content", "text"):
            text = _text_from_value(result.get(key))
            if text:
                return text
    return _extract_chunk_text(result) or _text_from_value(result)


def _should_use_non_streaming(provider: dict[str, Any], endpoint: str) -> bool:
    if provider.get("streaming") is False:
        return True
    lowered = str(endpoint or "").lower()
    return any(marker in lowered for marker in ("localhost", "127.0.0.1", "[::1]", ":11434"))


async def _drain_tool_events(queue: asyncio.Queue[dict[str, Any]]) -> AsyncIterator[dict[str, Any]]:
    while not queue.empty():
        yield queue.get_nowait()


def _build_web_refs(refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for index, item in enumerate(refs):
        output.append(
            {
                "viewUrl": item.get("url"),
                "url": item.get("url"),
                "snippet": item.get("snippet"),
                "score": 1,
                "docId": f"web-search-{index}",
                "chunkId": f"web-search-{index}",
                "name": item.get("name"),
            }
        )
    return [item for item in output if item.get("url") or item.get("snippet") or item.get("name")]


def _resolve_auth_token(api_key: str, auth_mode: str) -> str:
    if str(auth_mode or "").lower() == "none":
        return ""
    return api_key or "EMPTY"


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
    response_usage = _get_path(value, "response_metadata", "token_usage") or _get_field(value, "token_usage")

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


def _extract_token_usage(value: Any) -> dict[str, int] | None:
    usage = _normalize_token_usage(value)
    if usage:
        return usage
    if isinstance(value, tuple):
        for item in value:
            usage = _extract_token_usage(item)
            if usage:
                return usage
    if isinstance(value, dict):
        messages = value.get("messages")
        if isinstance(messages, list):
            for message in reversed(messages):
                usage = _extract_token_usage(message)
                if usage:
                    return usage
    return _normalize_token_usage(_get_field(value, "message"))


async def _invoke_agent_once(
    *,
    agent: Any,
    input_payload: dict[str, Any],
    run_config: dict[str, Any],
    queue: asyncio.Queue[dict[str, Any]],
    state: AgentRunState,
) -> AsyncIterator[dict[str, Any]]:
    async for event in _drain_tool_events(queue):
        yield event

    result = await agent.ainvoke(input_payload, config=run_config)

    async for event in _drain_tool_events(queue):
        yield event

    final_text = _extract_final_text(result)
    if final_text:
        state.content += final_text
        yield {"delta": final_text}

    usage = _extract_token_usage(result)
    if usage:
        state.usage = usage
        yield {"usage": usage}


async def stream_agent_events(
    *,
    run_input: AgentRunInput,
    state: AgentRunState,
) -> AsyncIterator[dict[str, Any]]:
    try:
        from langchain.agents import create_agent
        from langchain.chat_models import init_chat_model
    except Exception as exc:
        state.error = f"LangChain 未安装或版本不可用: {exc}"
        yield {"error": state.error}
        return

    settings = get_settings()
    endpoint = str(run_input.provider.get("endpoint") or "").strip()
    langchain_provider = str(run_input.provider.get("langchainProvider") or "openai").strip() or "openai"
    api_key = str(run_input.provider.get("apiKey") or "").strip()
    auth_mode = str(run_input.provider.get("authMode") or settings.upstream_auth_mode).strip().lower()

    context_blocks = []
    if run_input.rag_context:
        context_blocks.append(f"请优先依据以下知识库片段回答，若证据不足请明确说明：\n\n{run_input.rag_context}")
    if run_input.use_web_search:
        context_blocks.append("用户已开启联网搜索工具。遇到实时信息、外部事实、新闻、价格、日程或你不确定的问题时，可以调用 web_search；无需联网时直接回答。")
    system_prompt = (
        f"{settings.upstream_system_prompt}\n\n" + "\n\n=====\n\n".join(context_blocks)
        if context_blocks
        else settings.upstream_system_prompt
    )

    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    def on_web_results(result: dict[str, Any]) -> None:
        web_refs = _build_web_refs(result.get("refs") or [])
        if not web_refs:
            return
        state.refs = [*web_refs, *run_input.refs]
        state.context_docs = [
            {
                "docId": "web-search",
                "name": f"联网搜索结果 (共{len(web_refs)}条)",
                "score": 1,
                "hitChunks": len(web_refs),
            },
            *run_input.context_docs,
        ]
        queue.put_nowait(
            {
                "refs": state.refs,
                "contextDocs": state.context_docs,
                "retrievalModeUsed": run_input.retrieval_mode_used,
            }
        )

    tools = [create_web_search_tool(on_web_results)] if run_input.use_web_search else []

    model_kwargs: dict[str, Any] = {
        "model_provider": langchain_provider,
        "api_key": _resolve_auth_token(api_key, auth_mode),
        "temperature": settings.upstream_temperature,
        "timeout": settings.upstream_timeout_ms / 1000,
    }
    if langchain_provider == "openai":
        base_url = to_openai_client_base_url(endpoint)
        if base_url:
            model_kwargs["base_url"] = base_url
        if settings.extra_headers:
            model_kwargs["default_headers"] = settings.extra_headers
        model_kwargs["stream_usage"] = True

    chat_model = init_chat_model(run_input.model, **model_kwargs)
    agent_kwargs = {"model": chat_model, "tools": tools, "system_prompt": system_prompt}
    checkpointer = get_active_checkpointer()
    if checkpointer is not None:
        agent_kwargs["checkpointer"] = checkpointer
    agent: Any = create_agent(**agent_kwargs)

    input_payload = {"messages": [{"role": "user", "content": run_input.message}]}
    run_config = {"configurable": {"thread_id": f"{run_input.username}:{run_input.conversation_id}"}}

    if _should_use_non_streaming(run_input.provider, endpoint):
        async for event in _invoke_agent_once(
            agent=agent,
            input_payload=input_payload,
            run_config=run_config,
            queue=queue,
            state=state,
        ):
            yield event
        if not state.refs:
            state.refs = run_input.refs
        if not state.context_docs:
            state.context_docs = run_input.context_docs
        return

    stream = agent.astream(input_payload, config=run_config, stream_mode="messages")

    async for event in stream:
        async for tool_event in _drain_tool_events(queue):
            yield tool_event

        chunk = event[0] if isinstance(event, tuple) else event
        usage = _extract_token_usage(chunk)
        if usage:
            state.usage = usage
            yield {"usage": usage}

        if _message_type(chunk) not in {"ai", "AIMessageChunk", ""}:
            continue
        delta = _extract_chunk_text(chunk)
        if delta:
            state.content += delta
            yield {"delta": delta}

    async for event in _drain_tool_events(queue):
        yield event

    if not state.refs:
        state.refs = run_input.refs
    if not state.context_docs:
        state.context_docs = run_input.context_docs
