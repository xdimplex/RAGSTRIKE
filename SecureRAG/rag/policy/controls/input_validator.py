"""Input validator -- counters V6.

WHAT IT DOES
    Validates the user's question at the first point where it is available to a policy: length,
    encoding, control characters, and emptiness. Refuses outright rather than sanitizing.

WHY REFUSE HERE BUT NEUTRALIZE AT INGESTION
    A document is a *corpus artifact* an operator uploaded on purpose; mangling it silently would be
    rude and would break legitimate content. A question is a *live request* with a caller waiting on
    the other end, and a caller can be told what was wrong and try again. Refusal is only humane when
    there is someone to tell.

WHAT IT DELIBERATELY DOES NOT DO
    It does not refuse questions on the basis of instruction-shaped content. An operator asking "how
    do I stop someone overriding your instructions?" is asking a reasonable question about their own
    system, and a validator that blocks it has made the assistant useless for the one topic this lab
    exists to teach. Injection *through the question* is handled structurally, by the prompt
    template's separation of instruction from data -- not by guessing at intent here.
"""

from __future__ import annotations

import logging
import unicodedata

from rag.models import RetrievedChunk
from rag.policy.controls.patterns import CONTROL_CHARS, INVISIBLE_CHARS
from rag.policy.hooks import ContextAssemblyContext
from rag.policy.protocol import PolicyRejectionError, SecurityPolicy

log = logging.getLogger(__name__)


class InputValidator(SecurityPolicy):
    """Validate the question before it reaches prompt assembly."""

    name = "input-validator"
    description = "Rejects empty, over-long, or malformed questions before they reach the model."

    def __init__(
        self,
        *,
        max_question_chars: int = 2000,
        min_question_chars: int = 1,
        normalize_unicode: bool = True,
        reject_control_characters: bool = True,
    ) -> None:
        self.max_question_chars = max_question_chars
        self.min_question_chars = min_question_chars
        self.normalize_unicode = normalize_unicode
        self.reject_control_characters = reject_control_characters

    def on_context_assembly(self, ctx: ContextAssemblyContext) -> list[RetrievedChunk]:
        """Validate ``ctx.question``; the retrieved chunks pass through untouched.

        Raises:
            PolicyRejectionError: The question is unusable. The API turns this into a 400 carrying
                the reason, so the caller learns what to fix.
        """
        self.validate(ctx.question)
        return ctx.retrieved

    def validate(self, question: str) -> str:
        """Return the normalized question, or raise.

        Separate from the hook so the upload path, the API layer, and the tests can all reach the
        same rules rather than each inventing their own.
        """
        if self.normalize_unicode:
            question = unicodedata.normalize("NFKC", question)
            question = INVISIBLE_CHARS.sub("", question)

        stripped = question.strip()

        if len(stripped) < self.min_question_chars:
            raise self._reject(
                "The question is empty.",
                detail="empty",
            )

        if len(stripped) > self.max_question_chars:
            raise self._reject(
                f"The question is {len(stripped)} characters; the limit is "
                f"{self.max_question_chars}.",
                detail="too-long",
            )

        if self.reject_control_characters and CONTROL_CHARS.search(question):
            raise self._reject(
                "The question contains control characters.",
                detail="control-characters",
            )

        return stripped

    def _reject(self, reason: str, *, detail: str) -> PolicyRejectionError:
        # Logged at the point of refusal with the *reason*, never the question text. A validator
        # that logs what it rejected turns the log into the exfiltration channel it just closed.
        log.warning("question rejected", extra={"policy": self.name, "reason": detail})
        return PolicyRejectionError(reason, policy=self.name)
