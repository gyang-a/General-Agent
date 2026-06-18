from __future__ import annotations

import json
from collections.abc import AsyncIterator


def sse_event(payload: dict | str) -> str:
    if isinstance(payload, str):
        data = payload
    else:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"data: {data}\n\n"


async def sse_done() -> AsyncIterator[str]:
    yield "data: [DONE]\n\n"

