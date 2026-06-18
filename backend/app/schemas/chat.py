from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatStreamRequest(BaseModel):
    conversation_id: str = Field(default="", alias="conversationId")
    message: str = ""
    model: str = ""
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_mode: str = Field(default="hybrid", alias="retrievalMode")
    rag_top_k: int | None = Field(default=None, alias="ragTopK")
    use_web_search: bool = Field(default=False, alias="useWebSearch")

    class Config:
        populate_by_name = True

