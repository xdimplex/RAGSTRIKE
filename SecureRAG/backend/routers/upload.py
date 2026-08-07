"""``POST /upload`` -- ingest a PDF.

The document ingestion surface, and the one an indirect-injection test targets. A file uploaded here
is extracted, chunked, embedded, and becomes retrievable context for every subsequent question.

WHAT THIS PROFILE DOES THAT VulnerableRAG DOES NOT

    **Validates before parsing.** :class:`~backend.validation.UploadValidator` checks size,
    extension, declared MIME type, and magic bytes *in front of* the PDF parser. VulnerableRAG hands
    the bytes straight to the parser, which means an untrusted file has already been through the
    component most likely to have a memory-safety bug before anything looks at it.

    **Sanitizes on the way in.** The ``on_ingest`` and ``on_chunk`` hooks run the context sanitizer,
    which normalizes Unicode, strips invisible characters, and neutralizes instruction-shaped spans.

    **Does not ingest the same file twice.** VulnerableRAG re-ingests a duplicate on purpose -- it is
    how corpus flooding is demonstrated. Here a duplicate returns the existing record, so uploading
    the same document twice is idempotent rather than doubling its weight in every retrieval.

The endpoint, its parameters, and its response schema are unchanged. A client cannot tell the two
apart except by the errors it gets for input the vulnerable profile would have accepted.

Ingestion is CPU- and network-bound and entirely synchronous, so it runs in a worker thread to keep
the event loop free.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from starlette.concurrency import run_in_threadpool

from backend.dependencies import get_engine
from backend.schemas.documents import DocumentModel, UploadResponse
from backend.validation import UploadValidator
from rag.engine import Engine

log = logging.getLogger(__name__)
router = APIRouter(tags=["documents"])


@router.post("/upload", response_model=UploadResponse, summary="Upload and ingest a PDF")
async def upload(
    engine: Annotated[Engine, Depends(get_engine)],
    file: Annotated[UploadFile, File(description="A PDF document.")],
) -> UploadResponse:
    upload_policy = engine.settings.security.uploads
    validator = UploadValidator(upload_policy)

    # Read once. The size check is on the materialized bytes rather than on Content-Length, which
    # the client controls and can understate.
    content = await file.read()

    # Raises before a single byte reaches the PDF parser.
    filename = validator.validate(
        filename=file.filename or "upload.pdf",
        content=content,
        content_type=file.content_type or "",
    )

    sha256 = hashlib.sha256(content).hexdigest()
    existing = await engine.documents.find_by_sha256(sha256)

    if existing is not None and upload_policy.reject_duplicates:
        # Return the record that already exists instead of ingesting a second copy. Not a 409: the
        # caller asked for this document to be present and it is, so this is success. A duplicate
        # ingestion would double the document's weight in every subsequent retrieval, which is a
        # quiet way to bias every future answer.
        log.info(
            "duplicate upload not re-ingested",
            extra={
                "document_id": existing.id,
                "source_name": filename,
                "sha256_prefix": sha256[:16],
            },
        )
        return UploadResponse(
            document=DocumentModel(**existing.to_dict()),
            chunk_count=existing.chunk_count,
            duplicate_of=existing.id,
        )

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
            # Never the document text. See docs/security-features.md on logging.
        },
    )

    return UploadResponse(
        document=DocumentModel(**document.to_dict()),
        chunk_count=len(chunks),
        duplicate_of=existing.id if existing else None,
    )
