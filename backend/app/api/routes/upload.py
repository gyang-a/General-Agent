from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.dependencies import require_auth
from app.services.upload_service import save_upload

router = APIRouter(tags=["upload"])


@router.post("/api/upload")
async def upload(file: UploadFile = File(...), _: dict = Depends(require_auth)) -> dict:
    try:
        return {"ok": True, "file": await save_upload(file)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
