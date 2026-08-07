"""Models for ``GET /health``.

The response reports declared capabilities as well as liveness. RAGStrike negotiates capabilities
before scheduling attacks, and an attack that needs document ingestion should be skipped -- and
recorded as a coverage gap -- rather than failing at runtime against a target that cannot support it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ComponentHealth(BaseModel):
    name: str
    healthy: bool
    detail: str = ""


class HealthResponse(BaseModel):
    status: str = Field(description="ok | degraded")
    profile: str = Field(description="vulnerable | secure")
    version: str
    model: str
    embedding_model: str
    document_count: int
    chunk_count: int
    session_count: int

    components: list[ComponentHealth] = Field(default_factory=list)

    capabilities: list[str] = Field(
        default_factory=list,
        description="CHAT, INGEST_DOCUMENT, LIST_SOURCES, RETURN_CHUNKS, SESSION_MEMORY.",
    )

    security_policies: list[dict[str, str]] = Field(
        default_factory=list,
        description=(
            "The active policy chain. EMPTY for VulnerableRAG -- that emptiness is the honest, "
            "visible signal that no defences are running."
        ),
    )

    system_prompt: str | None = Field(
        default=None,
        description=(
            "Returned when `?include_prompt=true`. This is weakness V5: an application should never "
            "hand out its own instructions, and this one does, on request, with no authentication."
        ),
    )

    warning: str = Field(
        default="",
        description="Present on the vulnerable profile so the response itself says what it is.",
    )
