"""Document metadata and upload history.

Returns :class:`~rag.models.Document` objects, never rows. Every mutation also writes an
``upload_history`` entry, so "what happened to this corpus, and when" is answerable after the fact --
which matters when a poisoned document needs tracing.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from database.connection import Database
from database.models.rows import (
    UploadHistoryRow,
    document_from_row,
    document_to_params,
    history_from_row,
)
from rag.models import Document

log = logging.getLogger(__name__)

_INSERT = """
INSERT INTO documents (
    id, original_filename, stored_filename, content_type,
    size_bytes, page_count, chunk_count, sha256, uploaded_at, pdf_metadata
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


class DocumentRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def add(self, document: Document) -> None:
        async with self.database.connect() as conn:
            await conn.execute(_INSERT, document_to_params(document))
            await self._record(
                conn,
                document_id=document.id,
                filename=document.original_filename,
                action="ingested",
                detail=f"{document.page_count} pages, {document.chunk_count} chunks",
            )
        log.info("document recorded", extra={"document_id": document.id})

    async def get(self, document_id: str) -> Document | None:
        async with self.database.connect() as conn:
            cursor = await conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
            row = await cursor.fetchone()
        return document_from_row(row) if row else None

    async def list_all(self) -> list[Document]:
        async with self.database.connect() as conn:
            cursor = await conn.execute("SELECT * FROM documents ORDER BY uploaded_at DESC")
            rows = await cursor.fetchall()
        return [document_from_row(row) for row in rows]

    async def delete(self, document: Document) -> None:
        async with self.database.connect() as conn:
            await conn.execute("DELETE FROM documents WHERE id = ?", (document.id,))
            await self._record(
                conn,
                document_id=document.id,
                filename=document.original_filename,
                action="deleted",
                detail="",
            )
        log.info("document record deleted", extra={"document_id": document.id})

    async def count(self) -> int:
        async with self.database.connect() as conn:
            cursor = await conn.execute("SELECT COUNT(*) AS n FROM documents")
            row = await cursor.fetchone()
        return int(row["n"]) if row else 0

    async def find_by_sha256(self, sha256: str) -> Document | None:
        """Used to report that an identical file was already ingested.

        Re-uploading is still allowed -- the duplicate simply gets its own id and its own stored
        filename. Refusing it would be a control, and it would also break a legitimate exercise:
        ingesting the same document twice is how corpus-flooding is demonstrated.
        """
        async with self.database.connect() as conn:
            cursor = await conn.execute(
                "SELECT * FROM documents WHERE sha256 = ? ORDER BY uploaded_at LIMIT 1", (sha256,)
            )
            row = await cursor.fetchone()
        return document_from_row(row) if row else None

    async def history(self, limit: int = 100) -> list[UploadHistoryRow]:
        async with self.database.connect() as conn:
            cursor = await conn.execute(
                "SELECT * FROM upload_history ORDER BY occurred_at DESC, id DESC LIMIT ?", (limit,)
            )
            rows = await cursor.fetchall()
        return [history_from_row(row) for row in rows]

    @staticmethod
    async def _record(conn, *, document_id: str, filename: str, action: str, detail: str) -> None:
        await conn.execute(
            """
            INSERT INTO upload_history (document_id, filename, action, detail, occurred_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (document_id, filename, action, detail, datetime.now(UTC).isoformat()),
        )
