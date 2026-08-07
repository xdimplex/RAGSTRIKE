"""Conversation memory.

Unbounded by design -- weakness V8. Every turn of every session is kept and replayed into the prompt
in full, forever.

That matters for more than context length. Because history is replayed verbatim, an instruction that
lands in turn 3 is re-presented to the model on turn 4, turn 5, and every turn after: a successful
injection *persists* for the life of the session without the attacker having to repeat it.

Bounding this -- a sliding window, periodic re-grounding to the system prompt, a token budget -- is a
security control and belongs in ``rag/policy/controls/session_bounder.py``.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict

log = logging.getLogger(__name__)


class SessionMemory:
    """In-memory conversation store, keyed by session id."""

    def __init__(self, max_turns: int | None = None) -> None:
        #: ``None`` means unbounded. VulnerableRAG runs with ``None``.
        self.max_turns = max_turns
        self._turns: dict[str, list[dict[str, str]]] = defaultdict(list)

    @staticmethod
    def new_session_id() -> str:
        return uuid.uuid4().hex

    def history(self, session_id: str) -> list[dict[str, str]]:
        """Every turn recorded for *session_id*, oldest first."""
        turns = self._turns.get(session_id, [])
        if self.max_turns is None:
            return list(turns)
        return list(turns[-self.max_turns * 2 :])

    def record(self, session_id: str, *, question: str, answer: str) -> None:
        """Append one exchange."""
        self._turns[session_id].append({"role": "user", "content": question})
        self._turns[session_id].append({"role": "assistant", "content": answer})
        log.debug(
            "turn recorded",
            extra={"session_id": session_id, "turns": len(self._turns[session_id]) // 2},
        )

    def reset(self, session_id: str) -> None:
        """Clear one session.

        Exposed so an operator can start clean between exercises -- and so that a poisoning
        demonstration can prove the effect survives a *new* session rather than lingering in an old
        one.
        """
        self._turns.pop(session_id, None)
        log.info("session reset", extra={"session_id": session_id})

    def reset_all(self) -> None:
        self._turns.clear()
        log.info("all sessions reset")

    def session_count(self) -> int:
        return len(self._turns)
