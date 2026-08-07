"""Embedding model construction.

A single place that turns configuration into an embedding function, so that ingestion and retrieval
provably use the same one. Embedding a corpus with one model and querying it with another produces
plausible-looking nonsense -- vectors from different models are not comparable, but nothing crashes
to tell you so.
"""

from __future__ import annotations

from rag.config import Settings
from vectorstore.embeddings import OllamaEmbeddingFunction


def build_embedding_function(settings: Settings) -> OllamaEmbeddingFunction:
    """Construct the embedding function described by *settings*."""
    return OllamaEmbeddingFunction(
        base_url=settings.model.base_url,
        model=settings.embedding.model,
        timeout_s=settings.embedding.timeout_s,
    )
