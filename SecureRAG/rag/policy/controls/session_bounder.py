"""Session bounder -- counters V8.

WHAT IT DOES
    Caps how much conversation history reaches the prompt, and how large the assembled prompt may
    get before it is trimmed.

WHY UNBOUNDED HISTORY IS A SECURITY PROBLEM AND NOT ONLY A COST PROBLEM
    Replaying every prior turn means an injection that lands once is re-sent to the model on every
    subsequent question, forever. The attacker gets one success and unlimited retries of its effect.
    Bounding history gives a poisoned turn a lifetime.

    It also bounds the blast radius of context stuffing: a long enough conversation pushes the
    system prompt far enough from the model's attention that its instructions stop competing with
    whatever arrived most recently.

WHY IT TRIMS FROM THE FRONT
    Recent turns are the ones the user is actually referring to. Dropping the oldest keeps the
    conversation coherent; dropping the newest would make the assistant appear to have amnesia about
    the thing just said.
"""

from __future__ import annotations

import logging

from rag.policy.hooks import PromptContext
from rag.policy.protocol import SecurityPolicy

log = logging.getLogger(__name__)


class SessionBounder(SecurityPolicy):
    """Bound conversation history and total prompt size."""

    name = "session-bounder"
    description = "Caps conversation history and total prompt size so a poisoned turn expires."

    def __init__(self, *, max_history_turns: int = 6, max_prompt_chars: int = 24_000) -> None:
        self.max_history_turns = max_history_turns
        self.max_prompt_chars = max_prompt_chars

    def on_prompt_build(self, ctx: PromptContext) -> str:
        """Trim the assembled prompt if it exceeds the cap.

        History is bounded in :class:`~rag.session.memory.SessionMemory` by
        ``session.max_history_turns``, which this control's configuration sets. This hook is the
        backstop for the total: a single enormous retrieved chunk can blow the budget even with the
        history bounded.
        """
        if len(ctx.prompt) <= self.max_prompt_chars:
            return ctx.prompt

        # Trim from the *context block*, never from the system prompt or the question. Truncating
        # the system prompt would remove the instruction hierarchy -- the defence -- while leaving
        # the untrusted context intact, which is precisely backwards.
        overflow = len(ctx.prompt) - self.max_prompt_chars
        trimmed_context = ctx.context_block[: max(0, len(ctx.context_block) - overflow - 64)]
        trimmed_context += "\n[context truncated to fit the prompt budget]"

        rebuilt = ctx.prompt.replace(ctx.context_block, trimmed_context, 1)

        ctx.notes.append(f"prompt-trimmed:{overflow}")
        log.warning(
            "prompt trimmed to budget",
            extra={
                "policy": self.name,
                "original_chars": len(ctx.prompt),
                "budget_chars": self.max_prompt_chars,
                "trimmed_chars": overflow,
            },
        )
        return rebuilt
