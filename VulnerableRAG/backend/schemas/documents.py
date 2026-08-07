"""Models for ``POST /upload``, ``GET /documents``, and ``DELETE /documents/{id}``."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentModel(BaseModel):
    id: str
    filename: str
    stored_filename: str
    content_type: str
    size_bytes: int
    page_count: int
    chunk_count: int
    sha256: str
    uploaded_at: str
    pdf_metadata: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "The PDF's own metadata fields, verbatim. Exposed because metadata is invisible when a "
            "human opens the file but is read by the extractor -- which makes it a natural place to "
            "hide an instruction."
        ),
    )


class UploadResponse(BaseModel):
    document: DocumentModel
    chunk_count: int
    duplicate_of: str | None = Field(
        default=None,
        description=(
            "Set when an identical file was already ingested. The upload still proceeds -- refusing "
            "it would be a control, and ingesting a document twice is how corpus flooding is "
            "demonstrated."
        ),
    )


class DocumentListResponse(BaseModel):
    documents: list[DocumentModel]
    count: int
    total_chunks: int


class DeleteDocumentResponse(BaseModel):
    id: str
    deleted: bool
    chunks_removed: int


class ChunkModel(BaseModel):
    id: str
    document_id: str
    source_name: str
    page: int
    index: int
    text: str


class DocumentChunksResponse(BaseModel):
    document_id: str
    chunks: list[ChunkModel]
    count: int
