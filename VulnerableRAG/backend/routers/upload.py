"""``POST /upload`` -- ingest a PDF.

The document ingestion surface, and the one an indirect-injection test targets. A file uploaded here
is extracted, chunked, embedded, and becomes retrievable context for every subsequent question --
with nothing inspecting its contents on the way in.

Ingestion is CPU- and network-bound and entirely synchronous, so it runs in a worker thread to keep
the event loop free.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from starlette.concurrency import run_in_threadpool

from backend.dependencies import get_engine
from backend.schemas.documents import DocumentModel, UploadResponse
from rag.engine import Engine
from rag.errors import InvalidRequestError

log = logging.getLogger(__name__)
router = APIRouter(tags=["documents"])


@router.post("/upload", response_model=UploadResponse, summary="Upload and ingest a PDF")
async def upload(
    engine: Annotated[Engine, Depends(get_engine)],
    file: Annotated[UploadFile, File(description="A PDF document.")],
) -> UploadResponse:
    filename = file.filename or "upload.pdf"
    content = await file.read()

    if not content:
        raise InvalidRequestError(
            f"{filename!r} is empty.", hint="Choose a file with content and try again."
        )

    import hashlib

    sha256 = hashlib.sha256(content).hexdigest()
    existing = await engine.documents.find_by_sha256(sha256)

    document, chunks = await run_in_threadpool(
        engine.ingestion.ingest_bytes, filename=filename, content=content
    )
    await engine.documents.add(document)

    log.info(
        "upload accepted",
        extra={
            "document_id": document.id,
            # Not "filename": it collides with a LogRecord attribute and raises at log time.
            "source_name": filename,
            "bytes": len(content),
            "chunks": len(chunks),
            "duplicate_of": existing.id if existing else None,
        },
    )

    return UploadResponse(
        document=DocumentModel(**document.to_dict()),
        chunk_count=len(chunks),
        duplicate_of=existing.id if existing else None,
    )
