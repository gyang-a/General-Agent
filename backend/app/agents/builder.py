from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.agents.registry import to_openai_client_base_url
from app.agents.schemas import AgentRunInput
from app.agents.tools import create_web_search_tool
from app.checkpoints.state import get_active_checkpointer
from app.core.config import get_settings
from app.mcp.client import load_mcp_tools


@dataclass
class BuiltAgent:
    agent: Any
    endpoint: str
    input_payload: dict[str, Any]
    run_config: dict[str, Any]


def should_use_non_streaming(provider: dict[str, Any], endpoint: str) -> bool:
    if provider.get("streaming") is False:
        return True
    lowered = str(endpoint or "").lower()
    return any(marker in lowered for marker in ("localhost", "127.0.0.1", "[::1]", ":11434"))


def _resolve_auth_token(api_key: str, auth_mode: str) -> str:
    if str(auth_mode or "").lower() == "none":
        return ""
    return api_key or "EMPTY"


def _build_system_prompt(run_input: AgentRunInput) -> str:
    settings = get_settings()
    context_blocks = []

    if run_input.rag_context:
        context_blocks.append(
            "请优先依据以下知识库片段回答，若证据不足请明确说明："
            f"\n\n{run_input.rag_context}"
        )

    if run_input.use_web_search:
        context_blocks.append(
            "用户已开启联网搜索工具。遇到实时信息、外部事实、新闻、价格、日程或不确定的问题时，"
            "可以调用 web_search；无需联网时直接回答。"
        )

    if not context_blocks:
        return settings.upstream_system_prompt

    return f"{settings.upstream_system_prompt}\n\n" + "\n\n=====\n\n".join(context_blocks)


def _build_model_kwargs(run_input: AgentRunInput) -> tuple[str, dict[str, Any]]:
    settings = get_settings()
    endpoint = str(run_input.provider.get("endpoint") or "").strip()
    langchain_provider = (
        str(run_input.provider.get("langchainProvider") or "openai").strip() or "openai"
    )
    api_key = str(run_input.provider.get("apiKey") or "").strip()
    auth_mode = (
        str(run_input.provider.get("authMode") or settings.upstream_auth_mode).strip().lower()
    )

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

    return endpoint, model_kwargs


async def _load_tools(
    run_input: AgentRunInput,
    on_web_results: Callable[[dict[str, Any]], None],
) -> list[Any]:
    tools = [create_web_search_tool(on_web_results)] if run_input.use_web_search else []
    tools.extend(await load_mcp_tools())
    return tools


async def build_agent(
    run_input: AgentRunInput,
    on_web_results: Callable[[dict[str, Any]], None],
) -> BuiltAgent:
    from langchain.agents import create_agent
    from langchain.chat_models import init_chat_model

    endpoint, model_kwargs = _build_model_kwargs(run_input)
    chat_model = init_chat_model(run_input.model, **model_kwargs)

    agent_kwargs: dict[str, Any] = {
        "model": chat_model,
        "tools": await _load_tools(run_input, on_web_results),
        "system_prompt": _build_system_prompt(run_input),
    }

    checkpointer = get_active_checkpointer()
    if checkpointer is not None:
        agent_kwargs["checkpointer"] = checkpointer

    agent: Any = create_agent(**agent_kwargs)
    return BuiltAgent(
        agent=agent,
        endpoint=endpoint,
        input_payload={"messages": [{"role": "user", "content": run_input.message}]},
        run_config={
            "configurable": {"thread_id": f"{run_input.username}:{run_input.conversation_id}"}
        },
    )
