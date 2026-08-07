"""The assembled engine container.

Holds every collaborator a request handler needs, wired together once at startup.

This lives in the shared core rather than in a profile because it is **not profile-specific**: both
VulnerableRAG and SecureRAG produce one of these. What differs between them is the
``SecurityPolicyChain`` passed in, and nothing else (ADR-009).

Keeping it here also means the API routers can import it at runtime. They cannot annotate a
dependency with a type that only exists under ``TYPE_CHECKING`` -- FastAPI resolves annotations at
import time, and an unresolvable one is silently reinterpreted as a query parameter, which turns
every request into a 422 with no obvious cause.
"""

from __future__ import annotations

from dataclasses import dataclass

from database.connection import Database
from database.repositories.document_repository import DocumentRepository
from database.repositories.settings_repository import SettingsRepository
from rag.config import Settings
from rag.generation.llm_client import LLMClient
from rag.generation.pipeline import QueryPipeline
from rag.ingestion.pipeline import IngestionPipeline
from rag.policy.chain import SecurityPolicyChain
from rag.retrieval.retriever import Retriever
from rag.session.memory import SessionMemory
from vectorstore.collections import VectorStore


@dataclass
class Engine:
    """Everything a request handler needs."""

    settings: Settings
    policies: SecurityPolicyChain
    database: Database
    documents: DocumentRepository
    app_settings: SettingsRepository
    vector_store: VectorStore
    ingestion: IngestionPipeline
    retriever: Retriever
    query: QueryPipeline
    memory: SessionMemory
    llm_client: LLMClient

    @property
    def profile(self) -> str:
        return self.settings.profile
