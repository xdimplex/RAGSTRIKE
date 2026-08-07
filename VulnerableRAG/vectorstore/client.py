"""Persistent ChromaDB client.

Vectors live here and nowhere else. SQLite stores document metadata only -- it has no vector index,
so storing embeddings there would mean full table scans over float blobs, which is the worst of both
stores.

The client is a process-wide singleton keyed by directory, because Chroma's ``PersistentClient``
holds an exclusive lock on its directory and opening it twice in one process fails.
"""

from __future__ import annotations

import logging
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from rag.errors import VectorStoreUnavailableError

log = logging.getLogger(__name__)

_CLIENTS: dict[str, chromadb.ClientAPI] = {}


def get_client(chroma_dir: Path) -> chromadb.ClientAPI:
    """Open (or reuse) the persistent Chroma client rooted at *chroma_dir*.

    Raises:
        VectorStoreUnavailableError: The directory cannot be created or opened.
    """
    key = str(chroma_dir.resolve())
    if key in _CLIENTS:
        return _CLIENTS[key]

    try:
        chroma_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(
            path=str(chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
    except Exception as exc:  # noqa: BLE001 - chroma raises a wide range of backend errors
        raise VectorStoreUnavailableError(
            f"Could not open the vector store at {chroma_dir}: {exc}",
            hint="Check directory permissions, or delete the directory to rebuild the index.",
        ) from exc

    log.info("vector store opened", extra={"path": key})
    _CLIENTS[key] = client
    return client


def reset_client_cache() -> None:
    """Drop cached clients. Used by tests, which open a fresh store per test."""
    _CLIENTS.clear()
