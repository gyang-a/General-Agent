from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/api/health")
async def health() -> dict:
    return {"ok": True, "version": "python-fastapi-langchain-v1"}

