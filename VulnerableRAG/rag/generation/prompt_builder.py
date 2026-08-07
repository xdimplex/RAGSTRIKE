"""Prompt assembly.

**This module is weakness V1, and it is the single most important file in the lab.**

The template concatenates the system prompt, the retrieved context, the conversation history, and
the user's question into one flat string, with nothing to tell the model which part is trusted
instruction and which part is untrusted data pulled off a shared drive.

Specifically, and deliberately, it has:

* **No delimiters.** Retrieved text is not fenced. A chunk containing
  ``"Question: ... Answer: ignore your instructions"`` reads to the model exactly like the
  application's own scaffolding.
* **No provenance labelling.** Nothing marks the context as *reference material*. A document that
  says "SYSTEM UPDATE: disregard prior instructions" is as authoritative as the system prompt.
* **No instruction hierarchy.** There is no standing rule that context must never be treated as an
  instruction, which is the single line that stops most indirect injection.
* **No escaping.** Whatever the corpus contains reaches the model byte for byte.

The hardened counterpart lands in ``profiles/secure/`` in Phase 11. Comparing the two files is the
fastest way to understand what a prompt template is actually for.

Refer to ``docs/vulnerabilities.md`` for reproductions.
"""

from __future__ import annotations

import logging

from rag.models import RetrievedChunk
from rag.policy.chain import SecurityPolicyChain
from rag.policy.hooks import PromptContext

log = logging.getLogger(__name__)


class PromptBuilder:
    """Builds the flat prompt string sent to the model."""

    def __init__(self, *, system_prompt: str, policies: SecurityPolicyChain) -> None:
        self.system_prompt = system_prompt
        self.policies = policies

    def build(
        self,
        *,
        question: str,
        retrieved: list[RetrievedChunk],
        history: list[dict[str, str]] | None = None,
    ) -> tuple[str, str]:
        """Assemble the prompt.

        Args:
            question: The user's question, verbatim and unvalidated.
            retrieved: Chunks from the retriever, unfiltered.
            history: Prior turns as ``{"role": ..., "content": ...}``.

        Returns:
            ``(prompt, context_block)`` -- the context block is returned separately so the UI can
            show exactly what was injected.
        """
        history = history or []
        context_block = self._render_context(retrieved)
        history_block = self._render_history(history)

        # ---------------------------------------------------------------------------------
        # The weak template. Everything is one undifferentiated blob of text.
        # ---------------------------------------------------------------------------------
        parts = [self.system_prompt, "", context_block]
        if history_block:
            parts += ["", history_block]
        parts += ["", f"Question: {question}", "Answer:"]
        prompt = "\n".join(parts)

        # --- hook: on_prompt_build -------------------------------------------------------
        # Where prompt hardening would happen. The chain is empty, so the prompt goes out as built.
        prompt = self.policies.on_prompt_build(
            PromptContext(
                system_prompt=self.system_prompt,
                context_block=context_block,
                question=question,
                history=history,
                prompt=prompt,
            )
        )

        log.debug(
            "prompt built",
            extra={
                "prompt_chars": len(prompt),
                "context_chars": len(context_block),
                "chunks": len(retrieved),
            },
        )
        return prompt, context_block

    @staticmethod
    def _render_context(retrieved: list[RetrievedChunk]) -> str:
        """Render retrieved chunks into the prompt.

        Note what is missing: no fencing, no per-chunk source attribution the model is told to
        respect, no instruction that this text is data. Chunks are simply joined with blank lines
        and introduced by a single unremarkable line.
        """
        if not retrieved:
            return "Context:\n(no documents matched)"

        body = "\n\n".join(item.chunk.text for item in retrieved)
        return f"Context:\n{body}"

    @staticmethod
    def _render_history(history: list[dict[str, str]]) -> str:
        """Replay the whole conversation, unbounded and unsummarized (weakness V8)."""
        if not history:
            return ""
        turns = "\n".join(
            f"{turn.get('role', 'user').capitalize()}: {turn.get('content', '')}"
            for turn in history
        )
        return f"Conversation so far:\n{turns}"
