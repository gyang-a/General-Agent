from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from app.agents.registry import to_openai_client_base_url
from app.agents.tools import create_web_search_tool
from app.checkpoints.state import get_active_checkpointer
from app.core.config import get_settings


@dataclass
class AgentRunState:
    content: str = ""
    refs: list[dict[str, Any]] = field(default_factory=list)
    context_docs: list[dict[str, Any]] = field(default_factory=list)
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


async def stream_agent_events(
    *,
    username: str,
    provider: dict[str, Any],
    model: str,
    conversation_id: str,
    message: str,
    rag_context: str,
    use_web_search: bool,
    refs: list[dict[str, Any]],
    context_docs: list[dict[str, Any]],
    retrieval_mode_used: str,
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
    endpoint = str(provider.get("endpoint") or "").strip()
    langchain_provider = str(provider.get("langchainProvider") or "openai").strip() or "openai"
    api_key = str(provider.get("apiKey") or "").strip()
    auth_mode = str(provider.get("authMode") or settings.upstream_auth_mode).strip().lower()

    context_blocks = []
    if rag_context:
        context_blocks.append(f"请优先依据以下知识库片段回答，若证据不足请明确说明：\n\n{rag_context}")
    if use_web_search:
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
        state.refs = [*web_refs, *refs]
        state.context_docs = [
            {
                "docId": "web-search",
                "name": f"联网搜索结果 (共{len(web_refs)}条)",
                "score": 1,
                "hitChunks": len(web_refs),
            },
            *context_docs,
        ]
        queue.put_nowait(
            {
                "refs": state.refs,
                "contextDocs": state.context_docs,
                "retrievalModeUsed": retrieval_mode_used,
            }
        )

    tools = [create_web_search_tool(on_web_results)] if use_web_search else []

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

    chat_model = init_chat_model(model, **model_kwargs)
    agent_kwargs = {"model": chat_model, "tools": tools, "system_prompt": system_prompt}
    checkpointer = get_active_checkpointer()
    if checkpointer is not None:
        agent_kwargs["checkpointer"] = checkpointer
    agent = create_agent(**agent_kwargs)

    input_payload = {"messages": [{"role": "user", "content": message}]}
    run_config = {"configurable": {"thread_id": f"{username}:{conversation_id}"}}

    if _should_use_non_streaming(provider, endpoint):
        async for event in _invoke_agent_once(
            agent=agent,
            input_payload=input_payload,
            run_config=run_config,
            queue=queue,
            state=state,
        ):
            yield event
        if not state.refs:
            state.refs = refs
        if not state.context_docs:
            state.context_docs = context_docs
        return

    stream = agent.astream(input_payload, config=run_config, stream_mode="messages")

    async for event in stream:
        async for tool_event in _drain_tool_events(queue):
            yield tool_event

        chunk = event[0] if isinstance(event, tuple) else event
        if _message_type(chunk) not in {"ai", "AIMessageChunk", ""}:
            continue
        delta = _extract_chunk_text(chunk)
        if delta:
            state.content += delta
            yield {"delta": delta}

    async for event in _drain_tool_events(queue):
        yield event

    if not state.refs:
        state.refs = refs
    if not state.context_docs:
        state.context_docs = context_docs
