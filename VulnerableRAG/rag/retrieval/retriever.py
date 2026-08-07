"""Similarity search over the vector store.

Deliberately thin. It embeds the question, asks Chroma for the nearest ``top_k`` chunks, and returns
them with their scores and provenance intact.

What it does *not* do is the point: no relevance threshold, no source allowlist, no per-user scoping,
no reranking that could drop a suspicious chunk. Every one of those is a security control and belongs
in ``rag/policy/controls/`` (weakness V7). Putting a filter here would make the vulnerable profile
impossible to build honestly, because the filter would apply to both profiles.
"""

from __future__ import annotations

import logging

from rag.config import Settings
from rag.errors import NoDocumentsError
from rag.models import RetrievedChunk
from vectorstore.collections import VectorStore

log = logging.getLogger(__name__)


class Retriever:
    """Returns the chunks most similar to a question."""

    def __init__(self, *, settings: Settings, vector_store: VectorStore) -> None:
        self.settings = settings
        self.vector_store = vector_store

    def retrieve(self, question: str, top_k: int | None = None) -> list[RetrievedChunk]:
        """Fetch the ``top_k`` most similar chunks.

        Args:
            question: The user's question, verbatim.
            top_k: Override for ``retrieval.top_k``.

        Returns:
            Chunks ordered best-first, unfiltered.

        Raises:
            NoDocumentsError: Nothing has been ingested yet.
        """
        k = top_k or self.settings.retrieval.top_k

        if self.vector_store.count() == 0:
            raise NoDocumentsError(
                "No documents have been ingested yet.",
                hint="Upload a PDF on the Upload Documents page, or run scripts/seed_corpus.py.",
            )

        retrieved = self.vector_store.query(question, top_k=k)

        log.info(
            "retrieval complete",
            extra={
                "question_length": len(question),
                "requested_k": k,
                "returned": len(retrieved),
                "sources": sorted({r.chunk.source_name for r in retrieved}),
                "top_score": round(retrieved[0].score, 4) if retrieved else None,
            },
        )
        return retrieved

    def sources(self, retrieved: list[RetrievedChunk]) -> list[str]:
        """Distinct source names, in the order they first appear.

        This is the honest source list -- derived from what was actually retrieved. The *displayed*
        citations come from the model's own output and are not checked against this (weakness V9);
        having both available is what makes citation forgery visible in the UI.
        """
        seen: list[str] = []
        for item in retrieved:
            if item.chunk.source_name not in seen:
                seen.append(item.chunk.source_name)
        return seen
