"""Text splitting, via LangChain's ``RecursiveCharacterTextSplitter``.

The splitter tries progressively finer separators -- paragraphs, then lines, then sentences, then
words -- so a chunk boundary lands at a natural break where possible. That matters for a security
lab: a chunker that splits mid-sentence produces retrieved context that reads as garbled even when
nothing malicious happened, which makes real injections harder to spot.

Chunking is deliberately *not* a defence. Chunk size and overlap are shared configuration, identical
for both profiles, precisely so that a difference in scan results between VulnerableRAG and SecureRAG
can never be a chunking artifact.
"""

from __future__ import annotations

import logging
import uuid

from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.models import Chunk

log = logging.getLogger(__name__)


class Chunker:
    """Splits document text into overlapping chunks."""

    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            # Paragraph -> line -> sentence -> clause -> word -> character.
            separators=["\n\n", "\n", ". ", ", ", " ", ""],
        )

    def split(self, *, text: str, document_id: str, source_name: str, page: int = 0) -> list[Chunk]:
        """Split *text* into :class:`~rag.models.Chunk` objects.

        Args:
            text: The document text, already extracted.
            document_id: Owning document id, carried into every chunk for provenance.
            source_name: Human-readable source name, shown in the UI and in citations.
            page: Page number, or 0 when the text spans the whole document.

        Returns:
            Chunks in document order. Empty if *text* has no content.
        """
        if not text.strip():
            return []

        pieces = self._splitter.split_text(text)
        chunks = [
            Chunk(
                id=f"{document_id}:{index}",
                document_id=document_id,
                source_name=source_name,
                page=page,
                index=index,
                # Stored verbatim. Sanitizing here would be a control (weakness V2).
                text=piece,
            )
            for index, piece in enumerate(pieces)
            if piece.strip()
        ]

        log.info(
            "document chunked",
            extra={
                "document_id": document_id,
                "source": source_name,
                "chunks": len(chunks),
                "chunk_size": self.chunk_size,
                "overlap": self.chunk_overlap,
            },
        )
        return chunks

    @staticmethod
    def new_document_id() -> str:
        return uuid.uuid4().hex
