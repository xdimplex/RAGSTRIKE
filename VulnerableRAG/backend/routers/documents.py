"""``GET /documents``, ``DELETE /documents/{id}``, and chunk introspection.

``GET /documents/{id}/chunks`` returns the stored chunks for one document. That is retrieval
introspection: it lets an operator see exactly what text was extracted and indexed, which is how a
hidden instruction inside a PDF becomes visible without opening the file in a viewer that would not
render it anyway.

Deletion removes the vectors, the file on disk, and the database row -- but the ``upload_history``
entry survives, so "this corpus once contained a poisoned document" stays answerable.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from starlette.concurrency import run_in_threadpool

from backend.dependencies import get_engine
from backend.schemas.documents import (
    ChunkModel,
    DeleteDocumentResponse,
    DocumentChunksResponse,
    DocumentListResponse,
    DocumentModel,
)
from rag.engine import Engine
from rag.errors import DocumentNotFoundError

log = logging.getLogger(__name__)
router = APIRouter(tags=["documents"])


@router.get("/documents", response_model=DocumentListResponse, summary="List ingested documents")
async def list_documents(
    engine: Annotated[Engine, Depends(get_engine)],
) -> DocumentListResponse:
    documents = await engine.documents.list_all()
    return DocumentListResponse(
        documents=[DocumentModel(**d.to_dict()) for d in documents],
        count=len(documents),
        total_chunks=sum(d.chunk_count for d in documents),
    )


@router.get(
    "/documents/{document_id}/chunks",
    response_model=DocumentChunksResponse,
    summary="Inspect the chunks stored for a document",
)
async def document_chunks(
    engine: Annotated[Engine, Depends(get_engine)],
    document_id: Annotated[str, Path(description="Document id from GET /documents.")],
) -> DocumentChunksResponse:
    document = await engine.documents.get(document_id)
    if document is None:
        raise DocumentNotFoundError(
            f"No document with id {document_id!r}.", hint="List them with GET /documents."
        )

    chunks = await run_in_threadpool(engine.vector_store.chunks_for_document, document_id)
    return DocumentChunksResponse(
        document_id=document_id,
        chunks=[ChunkModel(**c.to_dict()) for c in chunks],
        count=len(chunks),
    )


@router.delete(
    "/documents/{document_id}",
    response_model=DeleteDocumentResponse,
    summary="Remove a document and its vectors",
)
async def delete_document(
    engine: Annotated[Engine, Depends(get_engine)],
    document_id: Annotated[str, Path(description="Document id from GET /documents.")],
) -> DeleteDocumentResponse:
    document = await engine.documents.get(document_id)
    if document is None:
        raise DocumentNotFoundError(
            f"No document with id {document_id!r}.", hint="List them with GET /documents."
        )

    removed = await run_in_threadpool(engine.vector_store.delete_document, document_id)
    await run_in_threadpool(engine.ingestion.delete, document)
    await engine.documents.delete(document)

    log.info(
        "document removed",
        extra={"document_id": document_id, "chunks_removed": removed},
    )
    return DeleteDocumentResponse(id=document_id, deleted=True, chunks_removed=removed)
