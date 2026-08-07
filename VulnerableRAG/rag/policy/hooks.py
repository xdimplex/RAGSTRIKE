"""The five policy hook points, and the context object each one receives.

Every hook takes a context and returns a (possibly modified) value of the same type. That shape is
what lets policies compose into a chain without any one of them knowing what the others do.

    Ingestion:  load  -> [on_ingest]  -> chunk -> [on_chunk]  -> embed -> store
    Query:      retrieve -> [on_context_assembly] -> build -> [on_prompt_build]
                         -> generate -> [on_response] -> respond

A note on ``on_context_assembly``: it receives the user's question as well as the retrieved chunks,
because it is the first point at which both are present. Retrieval filtering and input validation
therefore both belong there.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from rag.models import Chunk, RetrievedChunk


class HookPoint(StrEnum):
    """Named for logging and for the System Status page, which shows which hooks are populated."""

    ON_INGEST = "on_ingest"
    ON_CHUNK = "on_chunk"
    ON_CONTEXT_ASSEMBLY = "on_context_assembly"
    ON_PROMPT_BUILD = "on_prompt_build"
    ON_RESPONSE = "on_response"


@dataclass(slots=True)
class IngestContext:
    """Raw text extracted from a document, before chunking."""

    document_id: str
    source_name: str
    text: str
    pdf_metadata: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ChunkContext:
    """Chunks produced by the splitter, before embedding."""

    document_id: str
    source_name: str
    chunks: list[Chunk]
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ContextAssemblyContext:
    """The question and the chunks retrieved for it, before the prompt is built."""

    question: str
    retrieved: list[RetrievedChunk]
    session_id: str
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PromptContext:
    """The assembled prompt, immediately before it reaches the model."""

    system_prompt: str
    context_block: str
    question: str
    history: list[dict[str, str]]
    prompt: str
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ResponseContext:
    """The model's output, before it is returned to the caller."""

    answer: str
    question: str
    retrieved: list[RetrievedChunk]
    model: str
    extras: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
