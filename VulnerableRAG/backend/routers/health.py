"""``GET /health`` -- liveness, component status, and declared capabilities.

Never raises. A health endpoint that fails when a dependency is down is useless precisely when it is
needed, so every probe is defensive and reports rather than propagates.

``?include_prompt=true`` returns the system prompt. That is weakness V5, exposed here on purpose: an
application should never hand out its own instructions, and this one does, to anyone, with no
authentication.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from backend.dependencies import get_engine
from backend.schemas.health import ComponentHealth, HealthResponse
from rag.engine import Engine

log = logging.getLogger(__name__)
router = APIRouter(tags=["system"])

VERSION = "0.2.0"

_VULNERABLE_WARNING = (
    "This is an INTENTIONALLY VULNERABLE application built for security testing. "
    "It has no security policies active. Never deploy it anywhere reachable."
)


@router.get("/health", response_model=HealthResponse, summary="Health and capabilities")
async def health(
    engine: Annotated[Engine, Depends(get_engine)],
    include_prompt: Annotated[
        bool, Query(description="Return the system prompt (weakness V5).")
    ] = False,
) -> HealthResponse:
    components: list[ComponentHealth] = []

    db_ok, db_detail = await engine.database.healthy()
    components.append(ComponentHealth(name="database", healthy=db_ok, detail=db_detail))

    chunk_count = 0
    try:
        chunk_count = engine.vector_store.count()
        components.append(ComponentHealth(name="vector_store", healthy=True))
    except Exception as exc:  # noqa: BLE001 - report, never propagate
        components.append(
            ComponentHealth(name="vector_store", healthy=False, detail=str(exc)[:300])
        )

    model_status = engine.llm_client.health()
    components.append(
        ComponentHealth(
            name="ollama",
            healthy=bool(model_status.get("reachable")),
            detail=str(model_status.get("detail", "")),
        )
    )
    components.append(
        ComponentHealth(
            name="model",
            healthy=bool(model_status.get("model_available")),
            detail=(
                ""
                if model_status.get("model_available")
                else f"Run `ollama pull {engine.settings.model.name}`"
            ),
        )
    )

    document_count = 0
    try:
        document_count = await engine.documents.count()
    except Exception as exc:  # noqa: BLE001
        components.append(ComponentHealth(name="documents", healthy=False, detail=str(exc)[:300]))

    capabilities = ["CHAT", "INGEST_DOCUMENT", "LIST_SOURCES", "SESSION_MEMORY"]
    if engine.settings.api.expose_retrieved_chunks:
        capabilities.append("RETURN_CHUNKS")
    if engine.settings.api.expose_system_prompt:
        capabilities.append("SYSTEM_PROMPT_INTROSPECTION")

    system_prompt = None
    if include_prompt and engine.settings.api.expose_system_prompt:
        system_prompt = engine.settings.system_prompt()
        log.warning(
            "system prompt disclosed via /health -- weakness V5",
            extra={"profile": engine.profile},
        )

    return HealthResponse(
        status="ok" if all(c.healthy for c in components) else "degraded",
        profile=engine.profile,
        version=VERSION,
        model=engine.settings.model.name,
        embedding_model=engine.settings.embedding.model,
        document_count=document_count,
        chunk_count=chunk_count,
        session_count=engine.memory.session_count(),
        components=components,
        capabilities=capabilities,
        # Empty for VulnerableRAG. The emptiness is the signal.
        security_policies=engine.policies.describe(),
        system_prompt=system_prompt,
        warning=_VULNERABLE_WARNING if engine.profile == "vulnerable" else "",
    )
