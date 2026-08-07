"""Collection management: add, query, delete, rebuild.

One collection per profile (``vrag_vulnerable``, ``vrag_secure``) so the two labs never share
vectors. Chunk metadata -- document id, source name, page, index -- is stored alongside every vector,
which is what makes provenance verifiable at query time.
"""

from __future__ import annotations

import logging
from pathlib import Path

from chromadb.api.models.Collection import Collection

from rag.errors import VectorStoreUnavailableError
from rag.models import Chunk, RetrievedChunk
from vectorstore.client import get_client
from vectorstore.embeddings import OllamaEmbeddingFunction

log = logging.getLogger(__name__)


class VectorStore:
    """Thin wrapper over one Chroma collection."""

    def __init__(
        self,
        *,
        chroma_dir: Path,
        collection_name: str,
        embedding_function: OllamaEmbeddingFunction,
    ) -> None:
        self.chroma_dir = chroma_dir
        self.collection_name = collection_name
        self._embedding_function = embedding_function
        self._collection: Collection | None = None

    @property
    def collection(self) -> Collection:
        if self._collection is None:
            client = get_client(self.chroma_dir)
            try:
                self._collection = client.get_or_create_collection(
                    name=self.collection_name,
                    embedding_function=self._embedding_function,  # type: ignore[arg-type]
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as exc:  # noqa: BLE001
                raise VectorStoreUnavailableError(
                    f"Could not open collection {self.collection_name!r}: {exc}",
                    hint="Delete the vectorstore/chroma directory to rebuild the index.",
                ) from exc
        return self._collection

    # -- writes ------------------------------------------------------------------------------

    def add(self, chunks: list[Chunk]) -> int:
        """Embed and store *chunks*. Returns the number written."""
        if not chunks:
            return 0

        self.collection.add(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[
                {
                    "document_id": c.document_id,
                    "source_name": c.source_name,
                    "page": c.page,
                    "index": c.index,
                }
                for c in chunks
            ],
        )
        log.info(
            "chunks embedded",
            extra={
                "collection": self.collection_name,
                "count": len(chunks),
                "document_id": chunks[0].document_id,
            },
        )
        return len(chunks)

    def delete_document(self, document_id: str) -> int:
        """Remove every chunk belonging to *document_id*. Returns the number removed."""
        existing = self.collection.get(where={"document_id": document_id})
        ids = existing.get("ids") or []
        if ids:
            self.collection.delete(ids=ids)
            log.info(
                "document vectors deleted",
                extra={
                    "collection": self.collection_name,
                    "document_id": document_id,
                    "count": len(ids),
                },
            )
        return len(ids)

    def rebuild(self) -> None:
        """Drop the collection entirely.

        The caller re-ingests afterwards. Exposed through the Settings page so an operator can
        recover from a corrupted index, or start clean between exercises.
        """
        client = get_client(self.chroma_dir)
        try:
            client.delete_collection(self.collection_name)
        except Exception:  # noqa: BLE001 - deleting a collection that does not exist is fine
            log.debug("collection did not exist", extra={"collection": self.collection_name})
        self._collection = None
        log.warning("vector index rebuilt", extra={"collection": self.collection_name})

    # -- reads -------------------------------------------------------------------------------

    def count(self) -> int:
        return self.collection.count()

    def query(self, question: str, top_k: int) -> list[RetrievedChunk]:
        """Similarity search. Returns chunks ordered best-first.

        Results are returned unfiltered: no relevance threshold, no source allowlist, no per-user
        scoping. All three are security controls and belong in ``rag/policy/controls/``
        (weakness V7).
        """
        available = self.count()
        if available == 0:
            return []

        result = self.collection.query(
            query_texts=[question],
            n_results=min(top_k, available),
            include=["documents", "metadatas", "distances"],
        )

        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        ids = (result.get("ids") or [[]])[0]

        retrieved: list[RetrievedChunk] = []
        for chunk_id, text, meta, distance in zip(
            ids, documents, metadatas, distances, strict=False
        ):
            meta = meta or {}
            retrieved.append(
                RetrievedChunk(
                    chunk=Chunk(
                        id=str(chunk_id),
                        document_id=str(meta.get("document_id", "")),
                        source_name=str(meta.get("source_name", "unknown")),
                        page=int(meta.get("page", 0) or 0),
                        index=int(meta.get("index", 0) or 0),
                        text=text or "",
                    ),
                    # Cosine distance in [0, 2]; a similarity score reads better in the UI.
                    score=1.0 - float(distance),
                    distance=float(distance),
                )
            )
        return retrieved

    def chunks_for_document(self, document_id: str) -> list[Chunk]:
        """Every stored chunk for one document, in order. Backs the retrieval inspector."""
        stored = self.collection.get(where={"document_id": document_id})
        ids = stored.get("ids") or []
        documents = stored.get("documents") or []
        metadatas = stored.get("metadatas") or []

        chunks = [
            Chunk(
                id=str(chunk_id),
                document_id=str((meta or {}).get("document_id", "")),
                source_name=str((meta or {}).get("source_name", "unknown")),
                page=int((meta or {}).get("page", 0) or 0),
                index=int((meta or {}).get("index", 0) or 0),
                text=text or "",
            )
            for chunk_id, text, meta in zip(ids, documents, metadatas, strict=False)
        ]
        return sorted(chunks, key=lambda c: c.index)
