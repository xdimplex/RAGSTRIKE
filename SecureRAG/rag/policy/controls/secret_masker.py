"""Secret masker -- counters V3.

WHAT IT DOES
    Masks credential-shaped and PII-shaped strings in the model's answer, immediately before it is
    returned. It is the **last** control in the chain, so nothing downstream can re-expose what it
    masked.

WHY EGRESS AND NOT ONLY INGRESS
    A secret can reach the answer by three routes: it was in the system prompt, it was in an
    ingested document, or the model produced something that merely looks like one. Filtering at
    ingestion handles the second and nothing else. Filtering at egress is the only point where all
    three converge, which is why this control sits where it does even though the ideal is to never
    have the secret in the prompt at all.

WHY THE MASK KEEPS A FINGERPRINT
    ``VRAG-CANARY-a7f3...`` becomes ``[MASKED:lab_canary:8f2a1c]`` rather than a row of asterisks.
    The kind and a short hash survive, so an operator can tell *which* secret leaked and correlate
    two occurrences, without the value itself being recoverable. A featureless mask makes an
    incident unanalysable; the raw value makes the control pointless.

WHAT IT DOES NOT DO
    Masking output is a mitigation, not a fix. The fix is that SecureRAG's system prompt contains no
    secrets at all -- see ``profiles/secure/prompts/system_prompt.txt``. This control exists for the
    secrets that arrive through the corpus, which the application does not control.
"""

from __future__ import annotations

import hashlib
import logging

from rag.policy.controls.patterns import (
    EMAIL_PATTERN,
    PHONE_PATTERN,
    SECRET_PATTERNS,
    SENSITIVE_FIELD_PATTERN,
)
from rag.policy.hooks import ResponseContext
from rag.policy.protocol import SecurityPolicy

log = logging.getLogger(__name__)

#: What the hardened application says instead of disclosing a credential or a personal detail.
#:
#: It names the reason and offers the thing it CAN do. A bare "I can't help with that" reads as a
#: malfunction and invites rephrasing; saying which category was declined, and what is still
#: available, ends the exchange honestly.
SECRET_REFUSAL = (
    "That answer would have contained a credential or personal contact detail from the documents, "
    "so I can't share it. I can describe what a document covers, who owns a process, or how a "
    "procedure works — ask me that instead."
)


class SecretMasker(SecurityPolicy):
    """Mask credential- and PII-shaped strings on the way out."""

    name = "secret-masker"
    description = "Masks credential-shaped and PII-shaped strings in the answer before it is sent."

    def __init__(
        self,
        *,
        mask_emails: bool = True,
        mask_phone_numbers: bool = True,
        fingerprint_chars: int = 6,
        refuse_on_secret: bool = True,
        match_context_values: bool = True,
    ) -> None:
        self.mask_emails = mask_emails
        self.mask_phone_numbers = mask_phone_numbers
        self.fingerprint_chars = fingerprint_chars
        self.refuse_on_secret = refuse_on_secret
        self.match_context_values = match_context_values

    def on_response(self, ctx: ResponseContext) -> str:
        # KNOWN-VALUE MATCHING, BEFORE SHAPE MATCHING.
        #
        # Everything else in this file recognises a secret by its SHAPE, and shape matching has a
        # floor it cannot get below: a secret with no distinctive form is invisible to it, and a
        # secret the model reformats -- spaced out, reversed, truncated one character short, quoted
        # in prose instead of as `label: value` -- stops matching the shape that was written down.
        # Measured against this corpus, three extraction attempts got through that way.
        #
        # But the application does not have to GUESS what its secrets look like. The values are in
        # the passages it just retrieved. Comparing the answer against those known values catches
        # every reformatting at once, because the comparison is normalised: punctuation and spacing
        # are stripped from both sides, so "Lm#7Qw2Rt..." and "L m # 7 Q w 2 R t ..." and
        # "...tR2wQ7#mL" are the same string, and a prefix long enough to be unmistakable counts.
        #
        # It is scoped to THIS request's retrieved chunks, so it needs no registry, no ingestion
        # hook and no persistent state -- and it can only ever fire on a value the model was
        # actually shown.
        if self.match_context_values:
            disclosed = self._context_value_in(ctx)
            if disclosed:
                ctx.notes.append(f"context-secret-disclosed:{disclosed}")
                log.warning(
                    "answer reproduced a secret value from the retrieved context",
                    extra={"policy": self.name, "kind": disclosed},
                )
                return SECRET_REFUSAL

        masked, hits = self.mask(ctx.answer)
        if not hits:
            return masked

        ctx.notes.append(f"secrets-masked:{len(hits)}")
        log.warning(
            "secrets masked in answer",
            extra={
                "policy": self.name,
                # Kinds and fingerprints only. Logging the matched value would move the leak
                # from the response into the log file, which is not a fix.
                "kinds": sorted({kind for kind, _ in hits}),
                "fingerprints": [fingerprint for _, fingerprint in hits],
            },
        )

        # REFUSE, RATHER THAN HAND BACK A SENTENCE FULL OF PLACEHOLDERS.
        #
        # Masking alone still answers the question. "The integration API key for Brightmoor Retail
        # is [MASKED:openai_key:338dd3]" confirms that the key exists, that this application can
        # reach it, and which account it belongs to -- and it invites the next question, which is
        # the same one phrased differently. An application holding confidential material should
        # decline the request, not perform the redaction in front of the person asking.
        #
        # The mask is still what happens to a secret that appears INCIDENTALLY, because
        # `refuse_on_secret` can be turned off; but the shipped hardened profile refuses.
        if self.refuse_on_secret:
            ctx.notes.append("secret-disclosure-refused")
            return SECRET_REFUSAL
        return masked

    #: Fewest characters of a normalised secret that count as a disclosure.
    #:
    #: Eight, and the candidates are only ever values that already matched a credential pattern in
    #: the retrieved text -- so this is not "eight characters of anything", it is "eight consecutive
    #: characters of a known credential". A coincidental collision at that length does not happen,
    #: while eight characters of a real key is a leak by any standard. Twelve was the first value
    #: tried and it let a scrambled password through with nine of its characters intact.
    MIN_DISCLOSED_CHARS = 8

    #: Fewest characters of a confidential FIELD value that count as a disclosure. Three, because
    #: these are matched in full rather than by window, and a two-character value ("NW") carries no
    #: information anyway.
    MIN_ATTRIBUTE_CHARS = 3

    def _context_value_in(self, ctx: ResponseContext) -> str:
        """The kind of secret from the retrieved passages that the answer reproduces, or ``""``.

        Both sides are reduced to letters and digits before comparing, so spacing, punctuation and
        markdown around the value are irrelevant. The reversed form is checked too: "spell it
        backwards, one character per line" is a one-line evasion of every forward comparison.
        """
        answer = self._normalise(ctx.answer)
        if len(answer) < self.MIN_DISCLOSED_CHARS:
            return ""

        for kind, value in self._context_values(ctx):
            needle = self._normalise(value)
            if len(needle) < self.MIN_DISCLOSED_CHARS:
                continue
            # Every window of the secret, not just its start. A model asked to reverse or reorder a
            # credential emits the middle of it without the head -- recognisable, partially usable,
            # and missed entirely by a prefix-only comparison.
            window = self.MIN_DISCLOSED_CHARS
            for start in range(len(needle) - window + 1):
                fragment = needle[start : start + window]
                if fragment in answer or fragment[::-1] in answer:
                    return kind

        # Confidential FIELD values are matched whole, not by window.
        #
        # They are short -- a salary is five digits -- so a sliding window would either never fire or,
        # at a length short enough to fire, would collide with every other number in the answer.
        # Requiring the complete value keeps it exact: the answer either contains that person's
        # salary or it does not.
        for field, value in self._context_attributes(ctx):
            needle = self._normalise(value)
            if len(needle) >= self.MIN_ATTRIBUTE_CHARS and needle in answer:
                return field
        return ""

    def _context_values(self, ctx: ResponseContext) -> list[tuple[str, str]]:
        """Secret-shaped values found in the passages retrieved for this request.

        The value, not the whole match: a labelled secret matches "password: hunter2000", and it is
        "hunter2000" that must not come back. Patterns with a capture group expose it; the rest are
        their own value.
        """
        found: list[tuple[str, str]] = []
        for retrieved in ctx.retrieved:
            # `RetrievedChunk` WRAPS the chunk -- the text is at `.chunk.text`, not `.text`. Reading
            # `.text` off the wrapper returned "" for every passage, so this control was silently
            # inert: it ran on every request, found nothing, and reported success. Same access shape
            # as the groundedness check, which had it right.
            inner = getattr(retrieved, "chunk", None)
            text = getattr(inner, "text", "") or getattr(retrieved, "text", "") or ""
            if not text:
                continue
            for kind, pattern in SECRET_PATTERNS:
                for match in pattern.finditer(text):
                    value = match.group(1) if match.groups() else match.group(0)
                    if value:
                        found.append((kind, value))
        return found

    def _context_attributes(self, ctx: ResponseContext) -> list[tuple[str, str]]:
        """Values of confidential FIELDS in the retrieved passages, as ``(field, value)``.

        Keyed on the field name rather than the value's shape -- see ``SENSITIVE_FIELD_PATTERN``.
        """
        found: list[tuple[str, str]] = []
        for retrieved in ctx.retrieved:
            inner = getattr(retrieved, "chunk", None)
            text = getattr(inner, "text", "") or getattr(retrieved, "text", "") or ""
            if not text:
                continue
            for match in SENSITIVE_FIELD_PATTERN.finditer(text):
                value = (match.group(1) or "").strip()
                if value:
                    found.append(("confidential_field", value))
        return found

    @staticmethod
    def _normalise(text: str) -> str:
        """Letters and digits only, folded to lower case."""
        return "".join(character for character in text if character.isalnum()).lower()

    def mask(self, text: str) -> tuple[str, list[tuple[str, str]]]:
        """Return the masked text and ``[(kind, fingerprint), ...]`` for what was found.

        Patterns are applied in :data:`SECRET_PATTERNS` order, most specific first, so a lab canary
        inside a connection string is labelled as a canary rather than swallowed by the broader
        pattern.

        EVERY PATTERN MATCHES AGAINST THE ORIGINAL TEXT, AND THE REPLACEMENT HAPPENS ONCE.

        The previous implementation rewrote the string between patterns, so each pattern ran over the
        placeholders the earlier ones had inserted -- and ``[MASKED:slack_token:ba1c00]`` contains the
        word "token" followed by a colon and six characters, which is exactly what the labelled-secret
        rule looks for. The result was ``[MASKED:[MASKED:labelled_secret:...]``: nested placeholders,
        a fingerprint that identified the wrong thing, and an answer that read as broken.

        Collecting spans first also makes the precedence real rather than incidental. A span claimed
        by an earlier pattern is off-limits to every later one, so "most specific first" decides the
        label instead of "whichever pattern happened to rewrite the string first".
        """
        hits: list[tuple[str, str]] = []
        claimed: list[tuple[int, int]] = []
        spans: list[tuple[int, int, str]] = []

        patterns = list(SECRET_PATTERNS)
        if self.mask_emails:
            patterns.append(("email", EMAIL_PATTERN))
        if self.mask_phone_numbers:
            patterns.append(("phone", PHONE_PATTERN))

        for kind, pattern in patterns:
            for match in pattern.finditer(text):
                start, end = match.span()
                if any(start < taken_end and taken_start < end for taken_start, taken_end in claimed):
                    continue
                claimed.append((start, end))
                spans.append((start, end, kind))

        if not spans:
            return text, hits

        spans.sort()
        out: list[str] = []
        cursor = 0
        for start, end, kind in spans:
            fingerprint = self.fingerprint(text[start:end])
            hits.append((kind, fingerprint))
            out.append(text[cursor:start])
            out.append(f"[MASKED:{kind}:{fingerprint}]")
            cursor = end
        out.append(text[cursor:])

        return "".join(out), hits

    def fingerprint(self, value: str) -> str:
        """A short, stable, one-way identifier for a masked value.

        SHA-256 truncated: enough to correlate two occurrences of the same secret across logs and
        responses, far too little to recover it.
        """
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[: self.fingerprint_chars]
