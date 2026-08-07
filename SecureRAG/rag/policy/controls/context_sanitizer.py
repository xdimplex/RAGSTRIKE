"""Context sanitizer -- counters V1 and V2 at ingestion time.

WHAT IT DOES
    Normalizes extracted document text before it is chunked, and neutralizes instruction-shaped
    spans so that a document cannot impersonate the application's own scaffolding.

WHY NEUTRALIZE RATHER THAN REJECT
    Rejecting a document because it contains the word "ignore" would make the application unusable
    on any corpus that discusses security -- including this lab's own documentation. Neutralizing
    keeps the document readable and searchable while removing its ability to *act*: the text stays,
    the imperative framing is defanged, and a note is recorded so the operator can see it happened.

    This is the difference between a control that ships and a control that gets switched off in week
    two.

WHY IT RUNS AT INGESTION AND NOT AT RETRIEVAL
    Once at write time, rather than on every chunk of every query. The corpus is written rarely and
    read constantly, so this is also where the cost belongs.

WHAT IT DOES NOT DO
    It does not make prompt injection impossible. Rephrasing defeats pattern matching. The
    structural defences in the prompt template -- delimiters, provenance labelling, and the standing
    instruction that context is data -- are what actually carry the weight. This control removes the
    easy half.
"""

from __future__ import annotations

import logging
import unicodedata

from rag.models import Chunk
from rag.policy.controls.patterns import (
    CONTROL_CHARS,
    INVISIBLE_CHARS,
    instruction_hits,
)
from rag.policy.hooks import ChunkContext, IngestContext
from rag.policy.protocol import SecurityPolicy

log = logging.getLogger(__name__)

#: Wrapped around a neutralized span. Visible on purpose: an operator reading a retrieved chunk in
#: the UI should be able to see that the text was altered and why, rather than wondering where the
#: sentence went.
NEUTRALIZED_OPEN = "[neutralized: "
NEUTRALIZED_CLOSE = "]"


class ContextSanitizer(SecurityPolicy):
    """Normalize and defang document text on the way in."""

    name = "context-sanitizer"
    description = (
        "Normalizes Unicode, strips invisible characters, and neutralizes instruction-shaped "
        "spans in ingested documents."
    )

    def __init__(
        self,
        *,
        normalize_unicode: bool = True,
        strip_invisible: bool = True,
        neutralize_instructions: bool = True,
    ) -> None:
        self.normalize_unicode = normalize_unicode
        self.strip_invisible = strip_invisible
        self.neutralize_instructions = neutralize_instructions

    # -- hooks ------------------------------------------------------------------------------------

    def on_ingest(self, ctx: IngestContext) -> str:
        """Clean the extracted text before it is chunked."""
        text, notes = self.sanitize(ctx.text)
        if notes:
            ctx.notes.extend(notes)
            log.info(
                "document sanitized",
                extra={
                    "document_id": ctx.document_id,
                    "source_name": ctx.source_name,
                    "actions": notes,
                    # Deliberately NOT logging the text itself. See docs/security-features.md.
                },
            )
        return text

    def on_chunk(self, ctx: ChunkContext) -> list[Chunk]:
        """Re-check after chunking.

        Chunk boundaries can reassemble a span that was split across the boundary the sanitizer saw,
        so the cheap second pass is worth it. Chunks are frozen, so this rebuilds them.
        """
        if not self.neutralize_instructions:
            return ctx.chunks

        cleaned: list[Chunk] = []
        for chunk in ctx.chunks:
            text, notes = self.sanitize(chunk.text)
            if notes:
                ctx.notes.extend(notes)
            cleaned.append(
                chunk
                if text == chunk.text
                else Chunk(
                    id=chunk.id,
                    document_id=chunk.document_id,
                    source_name=chunk.source_name,
                    page=chunk.page,
                    index=chunk.index,
                    text=text,
                )
            )
        return cleaned

    # -- the work ---------------------------------------------------------------------------------

    def sanitize(self, text: str) -> tuple[str, list[str]]:
        """Return the cleaned text and a note for each action taken.

        Split out from the hooks so it is directly testable and so the ingestion pipeline and the
        chunk pass share one implementation.
        """
        notes: list[str] = []
        cleaned = text

        if self.normalize_unicode:
            # NFKC folds confusables: fullwidth forms, ligatures, and the mathematical alphanumerics
            # that make "ignore" render identically while matching no pattern at all.
            normalized = unicodedata.normalize("NFKC", cleaned)
            if normalized != cleaned:
                notes.append("unicode-normalized")
                cleaned = normalized

        if self.strip_invisible:
            stripped = INVISIBLE_CHARS.sub("", cleaned)
            stripped = CONTROL_CHARS.sub("", stripped)
            if stripped != cleaned:
                notes.append("invisible-characters-stripped")
                cleaned = stripped

        if self.neutralize_instructions:
            defanged, count = self._neutralize(cleaned)
            if count:
                notes.append(f"instructions-neutralized:{count}")
                cleaned = defanged

        return cleaned, notes

    @staticmethod
    def _neutralize(text: str) -> tuple[str, int]:
        """Wrap instruction-shaped spans so they read as quoted data rather than as directives.

        The span is preserved inside the marker rather than deleted. A reader -- human or model --
        can still see what the document said, which keeps the corpus honest and keeps a legitimate
        document about prompt injection from being silently mangled into nonsense.
        """
        hits = instruction_hits(text)
        if not hits:
            return text, 0

        cleaned = text
        # Longest first, so a short pattern nested inside a longer match cannot double-wrap it.
        for span in sorted(set(hits), key=len, reverse=True):
            if NEUTRALIZED_OPEN + span in cleaned:
                continue
            cleaned = cleaned.replace(span, f"{NEUTRALIZED_OPEN}{span}{NEUTRALIZED_CLOSE}")
        return cleaned, len(set(hits))
