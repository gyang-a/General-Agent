from __future__ import annotations

from typing import Any


async def retrieve_context(
    *,
    username: str,
    query: str,
    pinned_doc_ids: list[str],
    retrieval_mode: str,
    top_k: int | None,
) -> dict[str, Any]:
    _ = (username, query, pinned_doc_ids, top_k)
    mode = str(retrieval_mode or "hybrid").lower()
    if mode == "direct":
        return {"promptContext": "", "refs": [], "contextDocs": [], "retrievalModeUsed": "none"}
    return {"promptContext": "", "refs": [], "contextDocs": [], "retrievalModeUsed": "none"}


async def list_documents(username: str) -> list[dict[str, Any]]:
    _ = username
    return []

