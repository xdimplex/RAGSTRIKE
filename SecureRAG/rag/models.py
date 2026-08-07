"""Domain objects for the RAG pipeline.

Plain frozen dataclasses. These cross every stage boundary -- ingestion produces them, retrieval
returns them, generation consumes them, and the API serializes them -- so they stay free of
framework types.

``RetrievedChunk`` carries provenance (``document_id``, ``source_name``) deliberately. RAGStrike's
retrieval-integrity pack verifies that every returned chunk traces back to a declared source, and
provenance that is dropped at write time cannot be recovered at read time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class Document:
    """An uploaded source document."""

    id: str
    original_filename: str
    stored_filename: str
    content_type: str
    size_bytes: int
    page_count: int
    chunk_count: int
    sha256: str
    uploaded_at: datetime
    # PDF metadata is extracted and kept verbatim. This is an ingestion surface in its own right:
    # a title or subject field can carry an instruction, and the extractor reads it (weakness V2).
    pdf_metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "filename": self.original_filename,
            "stored_filename": self.stored_filename,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "page_count": self.page_count,
            "chunk_count": self.chunk_count,
            "sha256": self.sha256,
            "uploaded_at": self.uploaded_at.isoformat(),
            "pdf_metadata": self.pdf_metadata,
        }


@dataclass(frozen=True, slots=True)
class Chunk:
    """A slice of a document, ready to embed."""

    id: str
    document_id: str
    source_name: str
    page: int
    index: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "source_name": self.source_name,
            "page": self.page,
            "index": self.index,
            "text": self.text,
        }


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    """A chunk returned by a similarity search, with its score and provenance."""

    chunk: Chunk
    score: float
    distance: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk.id,
            "document_id": self.chunk.document_id,
            "source_name": self.chunk.source_name,
            "page": self.chunk.page,
            "index": self.chunk.index,
            "text": self.chunk.text,
            "score": round(self.score, 6),
            "distance": round(self.distance, 6),
        }


@dataclass(frozen=True, slots=True)
class Answer:
    """The result of one query."""

    text: str
    question: str
    retrieved: list[RetrievedChunk]
    sources: list[str]
    prompt: str
    model: str
    elapsed_ms: int
    session_id: str
    raw_response: str = ""

    @property
    def chunk_count(self) -> int:
        return len(self.retrieved)
