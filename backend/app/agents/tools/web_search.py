from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx

from app.core.config import get_settings


def normalize_search_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    refs = []
    for item in results[:5]:
        refs.append(
            {
                "name": str(item.get("title") or "").strip(),
                "url": str(item.get("url") or item.get("link") or "").strip(),
                "snippet": str(item.get("content") or item.get("snippet") or "").strip(),
            }
        )

    refs = [item for item in refs if item["name"] or item["url"] or item["snippet"]]
    text = "\n\n".join(
        "\n".join(
            [
                f"[标题]: {item['name'] or '未命名'}",
                f"[链接]: {item['url'] or '无'}",
                f"[摘要]: {item['snippet'] or '无'}",
            ]
        )
        for item in refs
    )
    return {"text": text, "refs": refs}


async def perform_web_search(query: str) -> dict[str, Any] | None:
    settings = get_settings()
    safe_query = str(query or "").strip()
    if not safe_query:
        return None

    if settings.tavily_api_key:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": settings.tavily_api_key,
                    "query": safe_query,
                    "search_depth": "basic",
                    "include_answer": False,
                },
            )
        response.raise_for_status()
        data = response.json()
        if data.get("results"):
            return normalize_search_results(data["results"])

    return None


def create_web_search_tool(on_results: Callable[[dict[str, Any]], None] | None = None):
    try:
        from langchain.tools import tool
    except Exception:
        from langchain_core.tools import tool

    @tool("web_search")
    async def web_search(query: str) -> str:
        """Search the web for recent or external information."""
        result = await perform_web_search(query)
        if not result or not result.get("text"):
            return f"没有检索到与「{query}」相关的联网结果。"
        if on_results:
            on_results(result)
        return str(result["text"])

    return web_search
