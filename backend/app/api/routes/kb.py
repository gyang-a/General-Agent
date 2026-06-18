from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile

from app.dependencies import require_auth
from app.services.rag_service import list_documents
from app.services.upload_service import save_upload

router = APIRouter(prefix="/api/kb", tags=["knowledge-base"])


@router.get("/docs")
async def docs(auth: dict = Depends(require_auth)) -> dict:
    return {"ok": True, "docs": await list_documents(auth["username"])}


@router.post("/upload")
async def kb_upload(file: UploadFile = File(...), _: dict = Depends(require_auth)) -> dict:
    try:
        return {"ok": True, "file": await save_upload(file, knowledge_base=True)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/docs/{doc_id}/view")
async def doc_view(doc_id: str, _: dict = Depends(require_auth)) -> Response:
    return Response(f"文档 {doc_id} 暂无可预览内容", media_type="text/plain; charset=utf-8")


@router.post("/docs/{doc_id}/reindex")
async def reindex(doc_id: str, _: dict = Depends(require_auth)) -> dict:
    return {"ok": True, "result": {"docId": doc_id, "status": "queued"}}


@router.delete("/docs/{doc_id}")
async def delete_doc(doc_id: str, _: dict = Depends(require_auth)) -> dict:
    _ = doc_id
    return {"ok": True}


@router.delete("/docs")
async def clear_docs(status: str = "", _: dict = Depends(require_auth)) -> dict:
    return {"ok": True, "result": {"status": status, "deletedCount": 0}}
