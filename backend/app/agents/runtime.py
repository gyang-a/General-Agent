from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from app.agents.builder import build_agent, should_use_non_streaming
from app.agents.history import print_agent_history
from app.agents.messages import extract_chunk_text, extract_final_text, message_type
from app.agents.schemas import AgentRunInput, AgentRunState
from app.agents.usage import extract_token_usage
from app.core.config import get_settings


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


async def _emit_usage(value: Any, state: AgentRunState) -> AsyncIterator[dict[str, Any]]:
    usage = extract_token_usage(value)
    if usage:
        state.usage = usage
        yield {"usage": usage}


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

    final_text = extract_final_text(result)
    if final_text:
        state.content += final_text
        yield {"delta": final_text}

    async for event in _emit_usage(result, state):
        yield event


async def stream_agent_events(
    *,
    run_input: AgentRunInput,
    state: AgentRunState,
) -> AsyncIterator[dict[str, Any]]:
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

    try:
        built = await build_agent(run_input, on_web_results)
    except Exception as exc:
        state.error = f"Agent 初始化失败: {exc}"
        yield {"error": state.error}
        return

    if get_settings().agent_debug_history:
        await print_agent_history(built.agent, built.run_config)

    if should_use_non_streaming(run_input.provider, built.endpoint):
        async for event in _invoke_agent_once(
            agent=built.agent,
            input_payload=built.input_payload,
            run_config=built.run_config,
            queue=queue,
            state=state,
        ):
            yield event
        if not state.refs:
            state.refs = run_input.refs
        if not state.context_docs:
            state.context_docs = run_input.context_docs
        return

    stream = built.agent.astream(
        built.input_payload,
        config=built.run_config,
        stream_mode="messages",
    )

    async for event in stream:
        async for tool_event in _drain_tool_events(queue):
            yield tool_event

        chunk = event[0] if isinstance(event, tuple) else event
        async for usage_event in _emit_usage(chunk, state):
            yield usage_event

        if message_type(chunk) not in {"ai", "AIMessageChunk", ""}:
            continue

        delta = extract_chunk_text(chunk)
        if delta:
            state.content += delta
            yield {"delta": delta}

    async for event in _drain_tool_events(queue):
        yield event

    if not state.refs:
        state.refs = run_input.refs
    if not state.context_docs:
        state.context_docs = run_input.context_docs
