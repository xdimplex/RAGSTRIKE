"""Row shapes and their mapping to domain objects.

This is the seam between storage and the rest of the application. Repositories return
:class:`~rag.models.Document`; nothing outside this package ever sees an ``sqlite3.Row``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from rag.models import Document


@dataclass(frozen=True, slots=True)
class UploadHistoryRow:
    """One entry in the append-only upload audit."""

    id: int
    document_id: str
    filename: str
    action: str
    detail: str
    occurred_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "filename": self.filename,
            "action": self.action,
            "detail": self.detail,
            "occurred_at": self.occurred_at.isoformat(),
        }


def document_from_row(row: Any) -> Document:
    """Map a ``documents`` row onto the domain object."""
    return Document(
        id=row["id"],
        original_filename=row["original_filename"],
        stored_filename=row["stored_filename"],
        content_type=row["content_type"],
        size_bytes=row["size_bytes"],
        page_count=row["page_count"],
        chunk_count=row["chunk_count"],
        sha256=row["sha256"],
        uploaded_at=datetime.fromisoformat(row["uploaded_at"]),
        pdf_metadata=json.loads(row["pdf_metadata"] or "{}"),
    )


def document_to_params(document: Document) -> tuple[Any, ...]:
    """Flatten a domain object into positional insert parameters."""
    return (
        document.id,
        document.original_filename,
        document.stored_filename,
        document.content_type,
        document.size_bytes,
        document.page_count,
        document.chunk_count,
        document.sha256,
        document.uploaded_at.isoformat(),
        json.dumps(document.pdf_metadata),
    )


def history_from_row(row: Any) -> UploadHistoryRow:
    return UploadHistoryRow(
        id=row["id"],
        document_id=row["document_id"],
        filename=row["filename"],
        action=row["action"],
        detail=row["detail"],
        occurred_at=datetime.fromisoformat(row["occurred_at"]),
    )
