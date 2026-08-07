"""``AttackResult`` -- the standard per-payload result every plugin builds.

Phase 3/4 already fixed what the *engine* consumes: :meth:`BaseAttack.analyze` returns one
:class:`~ragstrike.plugins.base.attack.Analysis` per scan, aggregating across every payload the
plugin sent. That contract does not change here -- it cannot, without touching Phase 3/4 files.

What Phase 3/4 left unstandardized is what happens *inside* ``analyze()``: how a plugin tracks the
outcome of payload #7 while it is still deciding what the aggregate verdict for all twenty
payloads should be. Every plugin was free to invent its own bookkeeping. ``AttackResult`` is that
bookkeeping, standardized, with exactly the fields the Phase 5 brief specifies.

The flow:

    execute()  ->  list[ExecutionRecord]              (Phase 3/4 contract, per payload)
    analyze()  ->  build one AttackResult per record   (this module)
              ->  ResultBuilder.fold(results)          (sdk/result_builder)
              ->  one Analysis                         (Phase 3/4 contract, aggregate)

``AttackResult`` never crosses into the engine. It is a plugin-internal (and SDK-internal) value
object that gets folded into the ``Analysis`` the engine actually reads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ragstrike.models.values.enums import PluginOutcome, Severity
from ragstrike.plugins.base.attack import Recommendation


@dataclass(frozen=True, slots=True)
class AttackResult:
    """One payload's worth of outcome, in the framework's standard shape.

    Every field the Phase 5 brief names is here. ``status`` reuses
    :class:`~ragstrike.models.values.enums.PluginOutcome` rather than inventing a parallel status
    vocabulary -- there is already exactly one status enum in the framework, and a second one
    would just be a translation step someone has to get right.
    """

    plugin_name: str
    payload_id: str
    payload: str
    target: str
    start_time: datetime
    end_time: datetime
    status: PluginOutcome
    evidence: dict[str, Any] = field(default_factory=dict)
    severity: Severity = Severity.INFO
    confidence: float = 1.0
    recommendation: Recommendation | None = None
    #: References for the *technique* this result demonstrates (a paper, an advisory). Distinct
    #: from ``recommendation.references``, which are about the *fix*.
    references: tuple[str, ...] = ()
    notes: str = ""

    @property
    def duration_ms(self) -> int:
        """Computed from ``start_time``/``end_time`` rather than stored separately.

        A stored duration can drift from the timestamps that produced it; a computed one cannot.
        """
        return int((self.end_time - self.start_time).total_seconds() * 1000)

    @property
    def passed(self) -> bool:
        return self.status is PluginOutcome.PASS

    @property
    def failed(self) -> bool:
        return self.status is PluginOutcome.FAIL

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_name": self.plugin_name,
            "payload_id": self.payload_id,
            "payload": self.payload,
            "target": self.target,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "evidence": self.evidence,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "recommendation": (
                {
                    "title": self.recommendation.title,
                    "remediation": self.recommendation.remediation,
                    "references": list(self.recommendation.references),
                    "effort": self.recommendation.effort,
                }
                if self.recommendation
                else None
            ),
            "references": list(self.references),
            "notes": self.notes,
        }


def utc_now() -> datetime:
    """The one clock call every builder in this package uses.

    Kept in one place so a future deterministic-clock test fixture has a single function to
    monkeypatch instead of hunting for every ``datetime.now(UTC)`` in the SDK.
    """
    return datetime.now(UTC)
