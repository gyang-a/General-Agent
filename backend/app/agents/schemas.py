from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


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
