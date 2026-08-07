"""The SecureRAG profile.

This module does two things: it builds the **full** security policy chain, and it assembles the
engine.

    SecurityPolicyChain(build_controls(settings.security, system_prompt=...))

**The chain is composed in code, not by configuration.** ``configs/security.yaml`` tunes thresholds
*within* controls; there is no value anywhere in it that removes a control from this list. That is
the mirror image of VulnerableRAG's empty chain, and it is deliberate for the same reason (ADR-009):
a posture that a config edit can silently change is a posture nobody can rely on.

Everything else in this file is identical to VulnerableRAG's ``profiles/vulnerable/profile.py``.
Comparing the two is the fastest way to see what hardening a RAG application actually consists of --
one line builds a different list, and the rest is the same application.
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
from rag.policy.controls import build_controls
from rag.retrieval.retriever import Retriever
from rag.session.memory import SessionMemory
from vectorstore.collections import VectorStore

log = logging.getLogger(__name__)

PROFILE_NAME = "secure"

__all__ = [
    "PROFILE_NAME",
    "Engine",
    "build_engine",
    "build_policy_chain",
    "require_lab_acknowledgement",
]


def build_policy_chain(settings: Settings) -> SecurityPolicyChain:
    """Return this profile's policy chain: every implemented control, in order.

    Takes ``settings`` because two controls need to be told things only the configuration knows --
    the thresholds, and the system prompt the output filter compares answers against. VulnerableRAG's
    equivalent takes no argument, because an empty list needs no configuration.
    """
    return SecurityPolicyChain(
        build_controls(settings.security, system_prompt=settings.system_prompt())
    )


def build_engine(
    *,
    settings: Settings | None = None,
    root: Path | None = None,
    llm_client: LLMClient | None = None,
) -> Engine:
    """Assemble the engine for this profile.

    Byte-for-byte the same as the vulnerable profile's, except for the ``build_policy_chain`` call
    and the log line. If these two functions ever diverge further, the differential comparison has
    started measuring something other than security.

    Args:
        settings: Pre-built settings. Loaded from YAML when omitted.
        root: Repository root, for tests running against a temp directory.
        llm_client: Substitute model client. Tests pass a scripted one so the whole API can run
            without Ollama.
    """
    settings = settings or load_settings(PROFILE_NAME, root=root)
    policies = build_policy_chain(settings)

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
    memory = SessionMemory(max_turns=settings.security.session.max_history_turns)
    client = llm_client or OllamaClient(settings)

    query = QueryPipeline(
        settings=settings,
        retriever=retriever,
        prompt_builder=PromptBuilder(system_prompt=settings.system_prompt(), policies=policies),
        llm_client=client,
        memory=memory,
        policies=policies,
    )

    log.info(
        "SECURE profile assembled -- %d security policies active: %s",
        len(policies),
        ", ".join(policy.name for policy in policies.policies),
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

    SecureRAG is the hardened half of the pair, so the obvious question is why it needs the same gate
    at all. Three reasons:

    **It is hardened, not audited.** Every control here is a control I wrote and tested against the
    attacks I thought of. That is not the same claim as "safe to expose", and the gate is what keeps
    the distinction from eroding into "the secure one, so it must be fine".

    **The pair must behave the same way operationally.** A lab where one half starts differently
    from the other is a lab where the difference between them is no longer only security.

    **It shares a corpus with the vulnerable half.** The same synthetic documents, including the
    planted canaries, are ingested here. That corpus belongs on loopback wherever it is loaded.
    """
    if os.environ.get("RAGSTRIKE_LAB_ACK") != "1":
        raise SystemExit(
            "\n"
            "  SecureRAG is the hardened half of a security lab. It is hardened, not audited,\n"
            "  and it is not a production application. It ingests the same synthetic corpus as\n"
            "  VulnerableRAG, canaries included.\n"
            "\n"
            "  Run it on loopback only, and never with real data.\n"
            "\n"
            "  Read docs/LAB_SAFETY.md, then set RAGSTRIKE_LAB_ACK=1 to start.\n"
        )
