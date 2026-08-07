"""Embedding function backed by Ollama.

Everything in this lab goes through Ollama -- the chat model and the embedding model both. That
keeps the setup to a single dependency the operator has already installed, avoids a second model
download at first use, and means the whole application works with no network access at all.

Implements ChromaDB's ``EmbeddingFunction`` protocol so it can be handed straight to a collection.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from rag.errors import ModelNotFoundError, ModelUnavailableError

log = logging.getLogger(__name__)


class OllamaEmbeddingFunction(EmbeddingFunction[Documents]):
    """Embeds text via Ollama's ``/api/embeddings`` endpoint.

    Subclasses Chroma's ``EmbeddingFunction`` rather than merely matching its call signature.
    Chroma persists ``get_config()`` alongside the collection and reconstructs the embedder from it
    on reopen, which is how it detects that a collection was built with a *different* model. That
    check matters: vectors from two different embedding models are not comparable, and querying
    across them produces plausible-looking nonsense with nothing crashing to say so.
    """

    def __init__(self, *, base_url: str, model: str, timeout_s: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

    @staticmethod
    def name() -> str:
        return "ollama-embedding"

    def get_config(self) -> dict[str, Any]:
        return {"base_url": self.base_url, "model": self.model, "timeout_s": self.timeout_s}

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> OllamaEmbeddingFunction:
        return OllamaEmbeddingFunction(
            base_url=config["base_url"],
            model=config["model"],
            timeout_s=config.get("timeout_s", 60),
        )

    def default_space(self) -> str:
        return "cosine"

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002 - Chroma's signature
        return [self.embed_one(text) for text in input]

    def embed_one(self, text: str) -> list[float]:
        """Embed a single string.

        Raises:
            ModelUnavailableError: Ollama is not reachable.
            ModelNotFoundError: Ollama is up but the embedding model is not pulled.
        """
        try:
            response = httpx.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=self.timeout_s,
            )
        except httpx.ConnectError as exc:
            raise ModelUnavailableError(
                f"Cannot reach Ollama at {self.base_url}.",
                hint="Start it with `ollama serve`, then retry.",
            ) from exc
        except httpx.TimeoutException as exc:
            raise ModelUnavailableError(
                f"Ollama did not respond within {self.timeout_s}s while embedding.",
                hint="The model may still be loading. Retry in a moment.",
            ) from exc

        if response.status_code == 404:
            raise ModelNotFoundError(
                f"Ollama does not have the embedding model {self.model!r}.",
                hint=f"Run `ollama pull {self.model}`.",
            )
        if response.status_code >= 400:
            raise ModelUnavailableError(
                f"Ollama returned {response.status_code} while embedding: {response.text[:200]}",
                hint="Check the Ollama server logs.",
            )

        payload: dict[str, Any] = response.json()
        vector = payload.get("embedding")
        if not vector:
            raise ModelUnavailableError(
                f"Ollama returned no embedding for model {self.model!r}.",
                hint=f"Confirm {self.model!r} is an embedding model, not a chat model.",
            )
        return [float(value) for value in vector]
