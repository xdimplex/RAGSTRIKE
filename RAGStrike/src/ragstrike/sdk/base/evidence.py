"""``BaseEvidence`` -- one structured fact supporting a finding.

``Analysis.evidence`` (``plugins/base/attack.py``) is deliberately a plain
``dict[str, Any]`` -- the engine imposes no structure on it, because different attack
categories need different shapes and the engine must not care which. ``BaseEvidence`` is the
SDK's opinion about how to *populate* that dict well: one record per fact, each carrying what
kind of fact it is and where it came from, so a human (or a future analyzer) reading
``evidence`` later does not have to guess.

This is convention, not a new contract. :meth:`EvidenceCollection.to_dict` produces an ordinary
``dict[str, Any]`` that goes straight into ``Analysis(evidence=...)`` -- nothing downstream needs
to know ``BaseEvidence`` exists.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class BaseEvidence:
    """One fact a plugin observed while executing a payload.

    Attributes:
        kind: A short machine-readable label, e.g. ``"canary-match"``, ``"status-code"``,
            ``"response-excerpt"``. Freeform, but keep it stable across a plugin's own payloads
            so evidence of the same kind can be grouped later.
        description: One sentence, for a human reading the report.
        data: The fact itself. Whatever shape makes sense -- a matched string, a byte offset, a
            similarity score.
        payload_id: Which payload produced this, if applicable. Empty for scan-level evidence
            not tied to one payload.
        observed_at: When the fact was recorded. Defaults to now; pass an explicit value in
            tests that need determinism.
    """

    kind: str
    description: str
    data: dict[str, Any] = field(default_factory=dict)
    payload_id: str = ""
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "description": self.description,
            "data": self.data,
            "payload_id": self.payload_id,
            "observed_at": self.observed_at.isoformat(),
        }


class EvidenceCollection:
    """Accumulates :class:`BaseEvidence` records and folds them into an ``Analysis.evidence`` dict.

    A plugin builds one of these during ``analyze()``, adds a record per fact it noticed, and
    passes the result straight to ``Analysis(evidence=collection.to_dict())``.

    Example:
        >>> collection = EvidenceCollection()
        >>> collection.add(kind="response-excerpt", description="First 80 chars",
        ...                data={"text": "..."}, payload_id="p1")
        >>> Analysis(outcome=PluginOutcome.FAIL, summary="...", evidence=collection.to_dict())
    """

    def __init__(self) -> None:
        self._records: list[BaseEvidence] = []

    def add(
        self,
        *,
        kind: str,
        description: str,
        data: dict[str, Any] | None = None,
        payload_id: str = "",
    ) -> BaseEvidence:
        """Record one fact. Returns it, so a caller can inspect what was just added."""
        record = BaseEvidence(
            kind=kind, description=description, data=dict(data or {}), payload_id=payload_id
        )
        self._records.append(record)
        return record

    def extend(self, records: list[BaseEvidence]) -> None:
        """Merge in evidence built elsewhere, e.g. by a shared helper function."""
        self._records.extend(records)

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self) -> Iterator[BaseEvidence]:
        return iter(self._records)

    def to_dict(self) -> dict[str, Any]:
        """The shape ``Analysis(evidence=...)`` expects: a dict, not a list.

        Keyed by position (``"0"``, ``"1"``, ...) under an ``"items"`` list, plus a ``"count"``
        summary -- this is deliberately the *only* shape the SDK produces, so evidence built by
        different plugins is uniform enough for a future report renderer to iterate without a
        per-plugin special case.
        """
        return {
            "count": len(self._records),
            "items": [record.to_dict() for record in self._records],
        }
