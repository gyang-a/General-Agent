from __future__ import annotations

from pydantic import BaseModel, Field


class CustomModelRequest(BaseModel):
    model_name: str = Field(default="", alias="modelName")
    api_key: str = Field(default="", alias="apiKey")
    endpoint: str = ""

    class Config:
        populate_by_name = True


class EmbeddingSourceRequest(BaseModel):
    source: str = "auto"

