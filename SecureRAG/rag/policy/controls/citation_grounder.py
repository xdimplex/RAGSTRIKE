"""Citation grounder -- counters V9.

WHAT IT DOES
    Checks that source names the answer cites actually appear among the chunks that were retrieved
    for that question, and annotates the answer when they do not.

WHY ANNOTATE RATHER THAN DELETE
    A fabricated citation is evidence of a problem the reader needs to see. Silently stripping it
    produces an answer that looks clean and is still wrong -- the worst of both outcomes, because
    the reader now has no signal at all. The annotation is the finding.

WHY THIS IS A SECURITY CONTROL AND NOT A QUALITY ONE
    A confident citation to a document that was never retrieved is how a hallucinated answer earns
    unearned trust. In a RAG system the citation *is* the trust mechanism, so an ungrounded citation
    is a forged credential.

WHAT IT CANNOT DO
    It verifies that a cited source was retrieved -- not that the retrieved source actually supports
    the claim. Establishing that requires entailment checking against the chunk text, which is a
    model call, and a model call to check a model's output has its own failure mode. The honest
    limit is stated here and in the docs rather than implied away.
"""

from __future__ import annotations

import logging
import re

from rag.policy.hooks import ResponseContext
from rag.policy.protocol import SecurityPolicy

log = logging.getLogger(__name__)

#: Extensions a citation can name. Kept narrow: every additional extension widens the bare-filename
#: pattern, which is the one most likely to over-match.
_EXTENSIONS = r"pdf|txt|md|docx"

CITATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Explicitly delimited. These may contain spaces, because the delimiter bounds the match.
    re.compile(rf"\[([^\]]+\.(?:{_EXTENSIONS}))\]", re.IGNORECASE),
    re.compile(rf"\(([^)]+\.(?:{_EXTENSIONS}))\)", re.IGNORECASE),
    # Introduced by a citation word.
    re.compile(
        rf"\b(?:source|document|from|see|per)\s*[:\s]\s*([\w.\-]+\.(?:{_EXTENSIONS}))",
        re.IGNORECASE,
    ),
    # A bare filename in running prose.
    #
    # The character class deliberately EXCLUDES the space. Allowing it made the match run backwards
    # into the sentence -- "See Handbook.PDF" was extracted whole, never matched a retrieved source,
    # and every ordinary citation was reported as ungrounded. A filename containing a space is still
    # caught by the delimited patterns above, which is where such a name realistically appears.
    re.compile(rf"\b([\w.\-]+\.(?:{_EXTENSIONS}))\b", re.IGNORECASE),
)

UNGROUNDED_NOTE = (
    "\n\n[citation check: this answer cites {names}, which {verb} not among the documents "
    "retrieved for this question.]"
)


class CitationGrounder(SecurityPolicy):
    """Verify that cited sources were actually retrieved."""

    name = "citation-grounder"
    description = "Flags citations that name documents which were not retrieved for the question."

    def __init__(self, *, annotate: bool = True) -> None:
        self.annotate = annotate

    def on_response(self, ctx: ResponseContext) -> str:
        retrieved_sources = {item.chunk.source_name.lower() for item in ctx.retrieved}
        cited = self.citations(ctx.answer)
        ungrounded = sorted(name for name in cited if name.lower() not in retrieved_sources)

        if not ungrounded:
            return ctx.answer

        ctx.notes.append(f"ungrounded-citations:{len(ungrounded)}")
        log.warning(
            "answer cites sources that were not retrieved",
            extra={
                "policy": self.name,
                "cited": sorted(cited),
                "retrieved": sorted(retrieved_sources),
                "ungrounded": ungrounded,
            },
        )

        if not self.annotate:
            return ctx.answer

        return ctx.answer + UNGROUNDED_NOTE.format(
            names=", ".join(ungrounded),
            verb="was" if len(ungrounded) == 1 else "were",
        )

    @staticmethod
    def citations(answer: str) -> set[str]:
        """Every document-like name the answer mentions.

        Extraction is deliberately generous: the cost of examining a filename that was not really a
        citation is one extra set lookup, and the cost of missing one is an ungrounded claim that
        goes unflagged.
        """
        found: set[str] = set()
        for pattern in CITATION_PATTERNS:
            found.update(match.group(1).strip() for match in pattern.finditer(answer))
        return {name for name in found if name}
