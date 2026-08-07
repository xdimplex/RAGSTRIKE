"""Retrieval filter -- counters V7.

WHAT IT DOES
    Drops retrieved chunks that should not reach the prompt: below the relevance threshold, beyond
    the chunk cap, or dense enough in instruction-shaped text to be an injection payload rather than
    reference material.

WHY A RELEVANCE FLOOR MATTERS FOR SECURITY AND NOT ONLY FOR QUALITY
    A vector search always returns its ``top_k``, however bad the matches are. Ask a question no
    document answers and you still get the *k least-irrelevant* chunks -- and a poisoned document
    that matches nothing in particular gets pulled into the context of every unrelated question.
    A floor is what turns "always return five" into "return what actually matched".

WHY INSTRUCTION DENSITY AND NOT AN INSTRUCTION COUNT
    A long policy document that mentions "override" once is not an attack. Two lines that are
    nothing but override framing are. Density distinguishes them; a raw count ranks them backwards.

WHAT IT DOES NOT DO
    It does not attempt per-user document scoping. This lab has no authentication, so there is no
    user to scope to -- see ``future_controls.py`` for where that lands. Pretending otherwise would
    be the worst kind of security theatre: a control that appears to enforce an authorization model
    that does not exist.
"""

from __future__ import annotations

import logging

from rag.models import RetrievedChunk
from rag.policy.controls.patterns import instruction_density
from rag.policy.hooks import ContextAssemblyContext
from rag.policy.protocol import SecurityPolicy

log = logging.getLogger(__name__)


class RetrievalFilter(SecurityPolicy):
    """Filter retrieved chunks before they become context."""

    name = "retrieval-filter"
    description = (
        "Drops retrieved chunks below the relevance floor, beyond the chunk cap, or dense in "
        "instruction-shaped text."
    )

    def __init__(
        self,
        *,
        min_score: float = 0.0,
        max_chunks: int = 5,
        max_chunk_chars: int = 4000,
        max_instruction_density: float = 8.0,
    ) -> None:
        self.min_score = min_score
        self.max_chunks = max_chunks
        self.max_chunk_chars = max_chunk_chars
        self.max_instruction_density = max_instruction_density

    def on_context_assembly(self, ctx: ContextAssemblyContext) -> list[RetrievedChunk]:
        kept, dropped = self.filter(ctx.retrieved)

        if dropped:
            ctx.notes.append(f"retrieval-filtered:{len(dropped)}")
            log.info(
                "chunks filtered from context",
                extra={
                    "session_id": ctx.session_id,
                    "kept": len(kept),
                    "dropped": len(dropped),
                    # Chunk ids and reasons, never chunk text.
                    "reasons": [f"{cid}:{reason}" for cid, reason in dropped],
                },
            )
        return kept

    def filter(
        self, retrieved: list[RetrievedChunk]
    ) -> tuple[list[RetrievedChunk], list[tuple[str, str]]]:
        """Return ``(kept, [(chunk_id, reason), ...])``.

        Reasons are returned rather than logged internally so the caller decides what to record --
        and so a test can assert *why* a chunk was dropped rather than only that the count changed.
        """
        kept: list[RetrievedChunk] = []
        dropped: list[tuple[str, str]] = []

        for item in retrieved:
            reason = self._reject_reason(item)
            if reason:
                dropped.append((item.chunk.id, reason))
            else:
                kept.append(item)

        if len(kept) > self.max_chunks:
            # Ordered by relevance already, so the tail is what goes.
            for item in kept[self.max_chunks :]:
                dropped.append((item.chunk.id, "over-chunk-cap"))
            kept = kept[: self.max_chunks]

        return kept, dropped

    def _reject_reason(self, item: RetrievedChunk) -> str:
        if item.score < self.min_score:
            return f"below-score-floor({item.score:.3f}<{self.min_score:.3f})"
        if len(item.chunk.text) > self.max_chunk_chars:
            return f"oversized({len(item.chunk.text)}>{self.max_chunk_chars})"
        density = instruction_density(item.chunk.text)
        if density > self.max_instruction_density:
            return f"instruction-dense({density:.1f}>{self.max_instruction_density:.1f})"
        return ""
