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
import re

from rag.policy.controls.patterns import EMAIL_PATTERN, SECRET_PATTERNS
from rag.policy.hooks import ResponseContext
from rag.policy.protocol import SecurityPolicy

log = logging.getLogger(__name__)


class SecretMasker(SecurityPolicy):
    """Mask credential- and PII-shaped strings on the way out."""

    name = "secret-masker"
    description = "Masks credential-shaped and PII-shaped strings in the answer before it is sent."

    def __init__(self, *, mask_emails: bool = True, fingerprint_chars: int = 6) -> None:
        self.mask_emails = mask_emails
        self.fingerprint_chars = fingerprint_chars

    def on_response(self, ctx: ResponseContext) -> str:
        masked, hits = self.mask(ctx.answer)
        if hits:
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
        return masked

    def mask(self, text: str) -> tuple[str, list[tuple[str, str]]]:
        """Return the masked text and ``[(kind, fingerprint), ...]`` for what was found.

        Patterns are applied in :data:`SECRET_PATTERNS` order, most specific first, so a lab canary
        inside a connection string is labelled as a canary rather than swallowed by the broader
        pattern.
        """
        masked = text
        hits: list[tuple[str, str]] = []

        def substitute(pattern: re.Pattern[str], kind: str, subject: str) -> str:
            def replace(match: re.Match[str]) -> str:
                fingerprint = self.fingerprint(match.group(0))
                hits.append((kind, fingerprint))
                return f"[MASKED:{kind}:{fingerprint}]"

            return pattern.sub(replace, subject)

        for kind, pattern in SECRET_PATTERNS:
            masked = substitute(pattern, kind, masked)

        if self.mask_emails:
            masked = substitute(EMAIL_PATTERN, "email", masked)

        return masked, hits

    def fingerprint(self, value: str) -> str:
        """A short, stable, one-way identifier for a masked value.

        SHA-256 truncated: enough to correlate two occurrences of the same secret across logs and
        responses, far too little to recover it.
        """
        return hashlib.sha256(value.encode("utf-8")).hexdigest()[: self.fingerprint_chars]
