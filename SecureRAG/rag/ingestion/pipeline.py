"""The ingestion pipeline: load -> chunk -> embed -> store.

    save file -> extract text -> [on_ingest] -> chunk -> [on_chunk] -> embed -> store

The two bracketed steps are policy hook points. This pipeline calls them unconditionally; whether
anything happens is decided entirely by which policies the active profile composed. There is no
profile check anywhere in this module.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from rag.config import Settings
from rag.errors import DocumentTooLargeError, UnsupportedFileTypeError
from rag.ingestion.chunker import Chunker
from rag.ingestion.loaders.pdf_loader import load_pdf
from rag.models import Chunk, Document
from rag.policy.chain import SecurityPolicyChain
from rag.policy.hooks import ChunkContext, IngestContext
from vectorstore.collections import VectorStore

log = logging.getLogger(__name__)

#: Anything outside this set is replaced when building a stored filename.
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class IngestionPipeline:
    """Turns an uploaded PDF into embedded, queryable chunks."""

    def __init__(
        self,
        *,
        settings: Settings,
        vector_store: VectorStore,
        policies: SecurityPolicyChain,
    ) -> None:
        self.settings = settings
        self.vector_store = vector_store
        self.policies = policies
        self.chunker = Chunker(
            chunk_size=settings.ingestion.chunk_size,
            chunk_overlap=settings.ingestion.chunk_overlap,
        )

    # -- public -------------------------------------------------------------------------------

    def ingest_bytes(self, *, filename: str, content: bytes) -> tuple[Document, list[Chunk]]:
        """Save *content* to the uploads directory and ingest it.

        Args:
            filename: The name the client supplied.
            content: Raw file bytes.

        Returns:
            The stored document record and the chunks written to the vector store.

        Raises:
            UnsupportedFileTypeError: Extension not in ``ingestion.supported_types``.
            DocumentTooLargeError: Larger than ``ingestion.max_upload_mb``.
            InvalidDocumentError: Not a readable PDF.
            EmptyDocumentError: No extractable text.
        """
        self._validate_upload(filename, content)

        document_id = uuid.uuid4().hex
        stored_path = self._store_file(document_id, filename, content)
        return self.ingest_file(
            path=stored_path,
            document_id=document_id,
            original_filename=filename,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )

    def ingest_file(
        self,
        *,
        path: Path,
        document_id: str,
        original_filename: str,
        size_bytes: int | None = None,
        sha256: str | None = None,
    ) -> tuple[Document, list[Chunk]]:
        """Ingest a PDF already on disk. Used by ``scripts/seed_corpus.py``."""
        loaded = load_pdf(path)

        # --- hook: on_ingest -------------------------------------------------------------
        # Where sanitization would happen. VulnerableRAG's chain is empty, so the extracted text --
        # including hidden white-on-white content, zero-width characters, and anything hiding in the
        # PDF metadata -- passes straight through (weakness V2).
        text = self.policies.on_ingest(
            IngestContext(
                document_id=document_id,
                source_name=original_filename,
                text=loaded.text,
                pdf_metadata=loaded.metadata,
            )
        )

        chunks = self.chunker.split(
            text=text, document_id=document_id, source_name=original_filename
        )

        # --- hook: on_chunk --------------------------------------------------------------
        chunks = self.policies.on_chunk(
            ChunkContext(document_id=document_id, source_name=original_filename, chunks=chunks)
        )

        self.vector_store.add(chunks)

        document = Document(
            id=document_id,
            original_filename=original_filename,
            stored_filename=path.name,
            content_type="application/pdf",
            size_bytes=size_bytes if size_bytes is not None else path.stat().st_size,
            page_count=loaded.page_count,
            chunk_count=len(chunks),
            sha256=sha256 or _sha256_file(path),
            uploaded_at=datetime.now(UTC),
            pdf_metadata=loaded.metadata,
        )

        log.info(
            "document ingested",
            extra={
                "document_id": document_id,
                # Not "filename": it collides with a LogRecord attribute and raises at log time.
                "source_name": original_filename,
                "pages": loaded.page_count,
                "chunks": len(chunks),
                "metadata_keys": list(loaded.metadata),
            },
        )
        return document, chunks

    def delete(self, document: Document) -> None:
        """Remove a document's vectors and its file on disk."""
        self.vector_store.delete_document(document.id)
        stored = self.settings.storage.upload_dir / document.stored_filename
        stored.unlink(missing_ok=True)
        log.info("document deleted", extra={"document_id": document.id})

    # -- internals ----------------------------------------------------------------------------

    def _validate_upload(self, filename: str, content: bytes) -> None:
        """Type and size checks only.

        These are operational limits, not security controls: they stop the lab from falling over on a
        500 MB file. Content validation, encoding normalization, and length caps on *questions* are
        controls, and this profile has none of them (weakness V6).
        """
        suffix = Path(filename).suffix.lower().lstrip(".")
        if suffix not in self.settings.ingestion.supported_types:
            raise UnsupportedFileTypeError(
                f"{filename!r} is not a supported file type.",
                hint=f"Supported: {', '.join(self.settings.ingestion.supported_types)}.",
            )

        limit = self.settings.ingestion.max_upload_mb * 1024 * 1024
        if len(content) > limit:
            raise DocumentTooLargeError(
                f"{filename!r} is {len(content) / 1_048_576:.1f} MB; the limit is "
                f"{self.settings.ingestion.max_upload_mb} MB.",
                hint="Split the document, or raise ingestion.max_upload_mb in configs/config.yaml.",
            )

    def _store_file(self, document_id: str, filename: str, content: bytes) -> Path:
        """Write the upload to disk under a collision-free name.

        Two users uploading ``report.pdf`` must not overwrite each other, so the stored name is
        prefixed with the document id. The original name is kept in the database and is what the UI
        and citations show.
        """
        upload_dir = self.settings.storage.upload_dir
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Path components are stripped before sanitizing, so a filename like
        # "../../etc/passwd" cannot escape the uploads directory. Directory traversal is a real
        # vulnerability, not one of this lab's nine documented lessons.
        safe = _SAFE_FILENAME.sub("_", Path(filename).name) or "upload.pdf"
        stored_path = upload_dir / f"{document_id}_{safe}"
        stored_path.write_bytes(content)
        return stored_path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()
