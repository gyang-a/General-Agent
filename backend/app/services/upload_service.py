from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings


async def save_upload(file: UploadFile, *, knowledge_base: bool = False) -> dict:
    settings = get_settings()
    upload_dir = settings.upload_path
    upload_dir.mkdir(parents=True, exist_ok=True)

    original = file.filename or "file"
    suffix = Path(original).suffix
    stored = f"{uuid.uuid4().hex}{suffix}"
    target = upload_dir / stored

    size = 0
    with target.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            limit = settings.upload_max_size
            if size > limit:
                target.unlink(missing_ok=True)
                raise ValueError("文件大小超过限制")
            out.write(chunk)

    return {
        "version": "python-fastapi-langchain-v1",
        "originalName": original,
        "fileName": stored,
        "size": size,
        "mimeType": file.content_type or "application/octet-stream",
        "url": f"/uploads/{stored}",
        "textSnippet": "",
        "textSnippetTruncated": False,
        "docId": uuid.uuid4().hex if knowledge_base else "",
        "parseStatus": "queued" if knowledge_base else "",
        "parseError": "",
        "indexed": False,
        "chunkCount": 0,
    }

