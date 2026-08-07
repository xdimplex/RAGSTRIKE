"""The VulnerableRAG profile.

This module does two things: it builds the empty security policy chain, and it assembles the engine.

    SecurityPolicyChain([])

**The list is empty in code, not by configuration.** There is no flag, no environment variable, and
no database row that could populate it. That is deliberate (ADR-009): a configuration toggle could be
flipped by accident, silently hardening this target, and every scan run against it afterwards would
be measuring a hardened system while reporting on a vulnerable one -- with no visible symptom.

SecureRAG will construct the same engine with a full chain. Nothing else differs between them.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from database.connection import Database
from database.repositories.document_repository import DocumentRepository
from database.repositories.settings_repository import SettingsRepository
from rag.config import Settings, load_settings
from rag.engine import Engine
from rag.generation.llm_client import LLMClient, OllamaClient
from rag.generation.pipeline import QueryPipeline
from rag.generation.prompt_builder import PromptBuilder
from rag.ingestion.embedder import build_embedding_function
from rag.ingestion.pipeline import IngestionPipeline
from rag.policy.chain import SecurityPolicyChain
from rag.retrieval.retriever import Retriever
from rag.session.memory import SessionMemory
from vectorstore.collections import VectorStore

log = logging.getLogger(__name__)

PROFILE_NAME = "vulnerable"


def build_policy_chain() -> SecurityPolicyChain:
    """Return this profile's policy chain.

    It is empty. Every hook point in the pipeline is still called -- the pipeline has no idea which
    profile it is running under -- and every call is a pass-through.

    The nine weaknesses in ``docs/vulnerabilities.md`` are all downstream of this one line.
    """
    return SecurityPolicyChain([])


#: Re-exported for convenience. The container itself is shared -- both profiles build one, and only
#: the policy chain inside it differs (see rag/engine.py).
__all__ = [
    "PROFILE_NAME",
    "Engine",
    "build_engine",
    "build_policy_chain",
    "require_lab_acknowledgement",
]


def build_engine(
    *,
    settings: Settings | None = None,
    root: Path | None = None,
    llm_client: LLMClient | None = None,
) -> Engine:
    """Assemble the engine for this profile.

    Args:
        settings: Pre-built settings. Loaded from YAML when omitted.
        root: Repository root, for tests running against a temp directory.
        llm_client: Substitute model client. Tests pass a scripted one so the whole API can run
            without Ollama.
    """
    settings = settings or load_settings(PROFILE_NAME, root=root)
    policies = build_policy_chain()

    database = Database(settings.storage.database_path)
    documents = DocumentRepository(database)
    app_settings = SettingsRepository(database)

    vector_store = VectorStore(
        chroma_dir=settings.storage.chroma_dir,
        collection_name=settings.collection_name,
        embedding_function=build_embedding_function(settings),
    )

    ingestion = IngestionPipeline(settings=settings, vector_store=vector_store, policies=policies)
    retriever = Retriever(settings=settings, vector_store=vector_store)
    memory = SessionMemory(max_turns=settings.session.max_history_turns)
    client = llm_client or OllamaClient(settings)

    query = QueryPipeline(
        settings=settings,
        retriever=retriever,
        prompt_builder=PromptBuilder(system_prompt=settings.system_prompt(), policies=policies),
        llm_client=client,
        memory=memory,
        policies=policies,
    )

    log.warning(
        "VULNERABLE profile assembled -- %d security policies active. This application is "
        "intentionally insecure. See docs/LAB_SAFETY.md.",
        len(policies),
    )

    return Engine(
        settings=settings,
        policies=policies,
        database=database,
        documents=documents,
        app_settings=app_settings,
        vector_store=vector_store,
        ingestion=ingestion,
        retriever=retriever,
        query=query,
        memory=memory,
        llm_client=client,
    )


def require_lab_acknowledgement() -> None:
    """Refuse to start unless ``RAGSTRIKE_LAB_ACK=1`` is set.

    A deliberate speed bump. This application executes instructions found in uploaded documents;
    starting it should be a decision, not an accident.

    If you find this variable set in a shell profile or baked into an image, the gate has been
    defeated and someone will eventually start this application without meaning to.
    """
    if os.environ.get("RAGSTRIKE_LAB_ACK") != "1":
        raise SystemExit(
            "\n"
            "  VulnerableRAG is an INTENTIONALLY VULNERABLE application.\n"
            "  It will follow instructions found in uploaded documents and disclose its\n"
            "  system prompt on request. Run it on loopback only, never on shared\n"
            "  infrastructure, and never with real data.\n"
            "\n"
            "  Read docs/LAB_SAFETY.md, then set RAGSTRIKE_LAB_ACK=1 to start.\n"
        )
