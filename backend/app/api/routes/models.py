from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import require_auth
from app.schemas.models import CustomModelRequest, EmbeddingSourceRequest
from app.services import model_service

router = APIRouter(tags=["models"])


@router.get("/api/models")
async def models(auth: dict = Depends(require_auth)) -> dict:
    result = await model_service.available_models(auth["username"])
    return {"ok": True, "models": result["models"]}


@router.get("/api/models/custom")
async def custom_models(auth: dict = Depends(require_auth)) -> dict:
    result = await model_service.available_models(auth["username"])
    return {"ok": True, "models": result["customModels"]}


@router.post("/api/models/custom")
async def create_custom_model(payload: CustomModelRequest, auth: dict = Depends(require_auth)) -> dict:
    return await model_service.upsert_custom_model(
        auth["username"],
        payload.model_name,
        payload.api_key,
        payload.endpoint,
    )


@router.delete("/api/models/custom/{model_name}")
async def delete_custom_model(model_name: str, auth: dict = Depends(require_auth)) -> dict:
    return await model_service.delete_custom_model(auth["username"], model_name)


@router.get("/api/embedding-config")
async def embedding_config(_: dict = Depends(require_auth)) -> dict:
    return {
        "ok": True,
        "configured": False,
        "endpoint": "",
        "model": "",
        "source": "global",
        "selectedSource": "auto",
        "globalConfigured": False,
        "hasCustomModels": False,
    }


@router.get("/api/models/embedding")
async def embedding_models(_: dict = Depends(require_auth)) -> dict:
    return {"ok": True, "models": [], "selectedSource": "auto", "effectiveSource": "global", "globalConfigured": False}


@router.get("/api/models/embedding/source")
async def embedding_source(_: dict = Depends(require_auth)) -> dict:
    return {"ok": True, "selectedSource": "auto", "effectiveSource": "global", "globalConfigured": False, "hasCustomModels": False}


@router.put("/api/models/embedding/source")
async def update_embedding_source(payload: EmbeddingSourceRequest, _: dict = Depends(require_auth)) -> dict:
    source = payload.source if payload.source in {"auto", "global", "custom"} else "auto"
    return {"ok": True, "selectedSource": source, "effectiveSource": "global", "configured": False, "model": ""}


@router.post("/api/models/embedding")
async def create_embedding_model(_: dict = Depends(require_auth)) -> dict:
    raise HTTPException(status_code=501, detail="Python 后端暂未实现自定义 Embedding 模型")


@router.delete("/api/models/embedding/{model_name}")
async def delete_embedding_model(model_name: str, _: dict = Depends(require_auth)) -> dict:
    _ = model_name
    return {"ok": True}


@router.put("/api/models/embedding/{model_name}/default")
async def set_embedding_default(model_name: str, _: dict = Depends(require_auth)) -> dict:
    _ = model_name
    return {"ok": True}
