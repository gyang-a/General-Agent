from __future__ import annotations

from fastapi import HTTPException

from app.agents.registry import (
    model_registry,
    normalize_custom_model_name,
    to_openai_compat_endpoint,
)
from app.repositories import get_repository
from app.utils.time import now_ms


async def get_user_custom_models(username: str) -> list[dict]:
    return await get_repository().get_custom_models(username)


async def available_models(username: str) -> dict:
    custom = await get_user_custom_models(username)
    names = list(model_registry.all_models)
    lower = {item.lower() for item in names}
    for item in custom:
        name = str(item.get("name") or "").strip()
        if name and name.lower() not in lower:
            names.append(name)
    return {
        "ok": True,
        "models": names,
        "customModels": [
            {
                "name": item.get("name"),
                "updatedAt": item.get("updatedAt"),
                "createdAt": item.get("createdAt"),
            }
            for item in custom
        ],
    }


async def resolve_selection_for_user(username: str, requested_model: str):
    requested = str(requested_model or "").strip()
    if requested:
        for item in await get_user_custom_models(username):
            if str(item.get("name") or "").lower() == requested.lower():
                return {
                    "provider": {
                        "id": f"user-model:{requested}",
                        "mode": "langchain",
                        "langchainProvider": "openai",
                        "endpoint": to_openai_compat_endpoint(str(item.get("endpoint") or "")),
                        "apiKey": str(item.get("apiKey") or ""),
                        "authMode": "bearer",
                    },
                    "model": str(item.get("name") or requested),
                }

    resolved = model_registry.resolve_selection(requested)
    if not resolved:
        return None
    provider, model_name = resolved
    return {"provider": provider.as_dict(), "model": model_name}


async def upsert_custom_model(username: str, model_name: str, api_key: str, endpoint: str) -> dict:
    safe_name = normalize_custom_model_name(model_name)
    if not safe_name or not api_key.strip() or not endpoint.strip():
        raise HTTPException(status_code=400, detail="接口地址、模型名称和 API Key 均为必填")
    if safe_name.lower() in {item.lower() for item in model_registry.all_models}:
        raise HTTPException(status_code=400, detail="模型名称与系统内置模型冲突，请更换名称")

    current = await get_user_custom_models(username)
    now = now_ms()
    updated = False
    next_models = []
    for item in current:
        if str(item.get("name") or "").lower() == safe_name.lower():
            next_models.append({**item, "name": safe_name, "apiKey": api_key, "endpoint": endpoint, "updatedAt": now})
            updated = True
        else:
            next_models.append(item)
    if not updated:
        next_models.append({"name": safe_name, "apiKey": api_key, "endpoint": endpoint, "createdAt": now, "updatedAt": now})
    await get_repository().set_custom_models(username, next_models)
    return {"ok": True, "model": {"name": safe_name, "updated": updated}}


async def delete_custom_model(username: str, model_name: str) -> dict:
    safe_name = normalize_custom_model_name(model_name)
    current = await get_user_custom_models(username)
    next_models = [item for item in current if str(item.get("name") or "").lower() != safe_name.lower()]
    await get_repository().set_custom_models(username, next_models)
    return {"ok": True}
