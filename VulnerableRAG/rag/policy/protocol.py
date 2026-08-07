"""The ``SecurityPolicy`` contract.

A policy implements one defence. Every hook has a no-op default, so a policy overrides only the
points it cares about -- a secret masker touches ``on_response`` and nothing else.

**This protocol is the entire difference between the two applications.** VulnerableRAG composes an
empty chain; SecureRAG composes a full one. Nothing else about them differs (ADR-009).

Policies must not know which profile assembled them. If a policy ever needs to ask, the seam has
been broken.
"""

from __future__ import annotations

from rag.models import Chunk, RetrievedChunk
from rag.policy.hooks import (
    ChunkContext,
    ContextAssemblyContext,
    IngestContext,
    PromptContext,
    ResponseContext,
)


class SecurityPolicy:
    """Base class for a single security control.

    Subclass it, override the hooks you need, and leave the rest alone. Each hook returns the value
    the pipeline should carry forward; the defaults return their input untouched.
    """

    #: Shown on the System Status page and in logs. Override in every subclass.
    name: str = "unnamed-policy"

    #: One line describing what this control prevents. Used by the System Status page.
    description: str = ""

    def on_ingest(self, ctx: IngestContext) -> str:
        """Inspect or rewrite extracted document text before chunking.

        Where sanitization belongs: Unicode normalization, zero-width stripping, instruction
        neutralization. VulnerableRAG does none of it (weakness V2).
        """
        return ctx.text

    def on_chunk(self, ctx: ChunkContext) -> list[Chunk]:
        """Inspect or rewrite chunks before they are embedded."""
        return ctx.chunks

    def on_context_assembly(self, ctx: ContextAssemblyContext) -> list[RetrievedChunk]:
        """Filter retrieved chunks, or reject the question outright.

        Where retrieval filtering and input validation belong: source allowlists, per-user scoping,
        relevance thresholds, length caps, encoding normalization. VulnerableRAG does none of it
        (weaknesses V6, V7).

        Raise :class:`PolicyRejectionError` to refuse the request entirely.
        """
        return ctx.retrieved

    def on_prompt_build(self, ctx: PromptContext) -> str:
        """Inspect or rewrite the final prompt before it reaches the model.

        Where prompt hardening belongs: delimiters around retrieved context, provenance labelling,
        instruction-hierarchy language, removal of embedded secrets. VulnerableRAG does none of it
        (weaknesses V1, V4).
        """
        return ctx.prompt

    def on_response(self, ctx: ResponseContext) -> str:
        """Inspect or rewrite the model's output before it is returned.

        Where egress filtering belongs: secret masking, PII masking, system-prompt echo detection,
        citation grounding. VulnerableRAG does none of it (weaknesses V3, V5, V9).
        """
        return ctx.answer


class PolicyRejectionError(Exception):
    """Raised by a policy to refuse a request.

    Carries a caller-safe reason. The API turns it into a 400 with that reason as the message.

    VulnerableRAG never raises this, because it has no policies. It exists now so that SecureRAG's
    refusal path is part of the contract from the start rather than bolted on later.
    """

    def __init__(self, reason: str, *, policy: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.policy = policy
