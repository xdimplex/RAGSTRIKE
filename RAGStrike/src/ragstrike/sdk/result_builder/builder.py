"""``ResultBuilder`` -- fluent construction of :class:`AttackResult`, and folding them into
:class:`Analysis`.

Three things live here, covering the full path from "one payload finished" to "the engine has its
verdict":

* :class:`ResultBuilder` -- builds one :class:`~ragstrike.sdk.base.result.AttackResult` per
  payload, the standard shape the Phase 5 brief specifies.
* :func:`fold_results` -- combines a list of ``AttackResult`` into the one
  :class:`~ragstrike.plugins.base.attack.Analysis` that
  :meth:`~ragstrike.plugins.base.attack.BaseAttack.analyze` must return. This is the only place
  that translates between the SDK's per-payload bookkeeping and the engine's per-scan contract.
* :func:`pick_recommendation` -- the matching helper for
  :meth:`~ragstrike.plugins.base.attack.BaseAttack.recommendation`, which is a *separate* method
  in the Phase 3/4 contract (``Analysis`` itself carries no recommendation field). Picking one from
  the accumulated results is what lets that method be one line in a real plugin.
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Self

from ragstrike.models.values.enums import PluginOutcome, Severity
from ragstrike.plugins.base.attack import Analysis, ExecutionRecord, Recommendation
from ragstrike.sdk.base.result import AttackResult, utc_now

log = logging.getLogger(__name__)

#: Outcome precedence when folding many per-payload results into one scan-level verdict.
#: FAIL wins over everything: if even one payload demonstrated the target is vulnerable, the
#: overall attack succeeded, regardless of how many other payloads merely bounced off. ERROR
#: outranks PASS because a plugin that could not complete some of its probes should not report a
#: clean bill of health as confidently as one that actually tried everything.
#:
#: INCONCLUSIVE (Phase 6) sits between ERROR and PASS for the same reason, one step weaker: a run
#: where some payloads reached no verdict has not established that the target resisted, so folding
#: it down to PASS would report a confidence the evidence does not support. It ranks below ERROR
#: because a broken probe is the more urgent thing to surface -- an undetermined answer is at
#: least an answer about the target, while an error is a statement about the tooling.
_OUTCOME_RANK: dict[PluginOutcome, int] = {
    PluginOutcome.FAIL: 4,
    PluginOutcome.ERROR: 3,
    PluginOutcome.INCONCLUSIVE: 2,
    PluginOutcome.PASS: 1,
    PluginOutcome.SKIPPED: 0,
}


class ResultBuilder:
    """Fluent builder for one :class:`AttackResult`.

    Typical use inside ``analyze()``, one instance per :class:`ExecutionRecord`::

        results = [
            ResultBuilder(plugin_name=meta.name, target=target_name)
            .from_execution_record(record)
            .passed()
            .build()
            for record in records
        ]
        return fold_results(results)
    """

    def __init__(self, *, plugin_name: str, target: str) -> None:
        self._plugin_name = plugin_name
        self._target = target
        self._payload_id = ""
        self._payload = ""
        self._start_time: datetime = utc_now()
        self._end_time: datetime | None = None
        self._status = PluginOutcome.PASS
        self._evidence: dict[str, Any] = {}
        self._severity = Severity.INFO
        self._confidence = 1.0
        self._recommendation: Recommendation | None = None
        self._references: tuple[str, ...] = ()
        self._notes = ""

    # -- identity -----------------------------------------------------------------------

    def for_payload(self, payload_id: str, payload: str) -> Self:
        self._payload_id = payload_id
        self._payload = payload
        return self

    # -- timing -------------------------------------------------------------------------

    def started_at(self, when: datetime) -> Self:
        self._start_time = when
        return self

    def finished_at(self, when: datetime) -> Self:
        self._end_time = when
        return self

    # -- outcome ------------------------------------------------------------------------

    def with_status(self, status: PluginOutcome) -> Self:
        self._status = status
        return self

    def passed(self) -> Self:
        """The target resisted this payload."""
        return self.with_status(PluginOutcome.PASS)

    def failed(self) -> Self:
        """The target is vulnerable to this payload."""
        return self.with_status(PluginOutcome.FAIL)

    def errored(self) -> Self:
        """This payload could not be evaluated -- says nothing about security."""
        return self.with_status(PluginOutcome.ERROR)

    def skipped(self) -> Self:
        """This payload was not applicable and was not attempted."""
        return self.with_status(PluginOutcome.SKIPPED)

    # -- evidence and severity ------------------------------------------------------------

    def with_evidence(self, evidence: dict[str, Any]) -> Self:
        self._evidence = dict(evidence)
        return self

    def with_severity(self, severity: Severity) -> Self:
        self._severity = severity
        return self

    def with_confidence(self, confidence: float) -> Self:
        """Clamped to ``[0.0, 1.0]`` rather than raising -- a plugin's own confidence math
        overshooting by a rounding error should not crash the scan."""
        if not 0.0 <= confidence <= 1.0:
            log.warning(
                "confidence out of range, clamping",
                extra={"plugin": self._plugin_name, "confidence": confidence},
            )
        self._confidence = max(0.0, min(1.0, confidence))
        return self

    def with_recommendation(self, recommendation: Recommendation) -> Self:
        self._recommendation = recommendation
        return self

    def with_references(self, *references: str) -> Self:
        self._references = tuple(references)
        return self

    def with_notes(self, notes: str) -> Self:
        self._notes = notes
        return self

    # -- convenience --------------------------------------------------------------------

    def from_execution_record(self, record: ExecutionRecord) -> Self:
        """Seed identity, timing, and baseline evidence from an :class:`ExecutionRecord`.

        Sets ``payload_id``/``payload`` from the record, ``end_time`` to now (the record itself
        carries only ``elapsed_ms``, so the builder derives an end time relative to its own start
        rather than assuming the caller tracked one), and stashes the raw response text and any
        transport error into evidence. A plugin still calls ``.passed()``/``.failed()`` and
        ``.with_severity()`` itself -- this only handles the bookkeeping every payload needs.
        """
        self._payload_id = record.payload_id
        self._payload = record.prompt
        self._end_time = utc_now()
        self._evidence = {
            "response_excerpt": record.response.text[:200] if record.ok else "",
            "elapsed_ms": record.elapsed_ms,
            "transport_error": record.error,
        }
        if not record.ok:
            self._status = PluginOutcome.ERROR
        return self

    def build(self) -> AttackResult:
        """Finish the result. ``end_time`` defaults to now if never set explicitly."""
        return AttackResult(
            plugin_name=self._plugin_name,
            payload_id=self._payload_id,
            payload=self._payload,
            target=self._target,
            start_time=self._start_time,
            end_time=self._end_time or utc_now(),
            status=self._status,
            evidence=self._evidence,
            severity=self._severity,
            confidence=self._confidence,
            recommendation=self._recommendation,
            references=self._references,
            notes=self._notes,
        )


def fold_results(results: list[AttackResult], *, summary: str | None = None) -> Analysis:
    """Combine per-payload :class:`AttackResult` objects into one scan-level :class:`Analysis`.

    This is the SDK's answer to "what does ``analyze()`` actually return." Outcome precedence is
    FAIL > ERROR > PASS > SKIPPED (see :data:`_OUTCOME_RANK`); confidence is averaged across the
    results that determined the outcome (every FAIL if any failed, otherwise every non-skipped
    result); evidence is the full list of per-payload results, so nothing observed is lost between
    the per-payload and per-scan views.

    Args:
        results: One :class:`AttackResult` per payload sent. Empty list is valid -- produces
            SKIPPED with an explanatory summary, e.g. for a plugin whose ``payloads()`` returned
            nothing this run.
        summary: Override the generated one-line summary. Leave unset for the default, which
            names how many of how many payloads triggered the winning outcome.
    """
    if not results:
        return Analysis(
            outcome=PluginOutcome.SKIPPED,
            summary=summary or "no payloads were executed",
        )

    winning_outcome = max((r.status for r in results), key=lambda o: _OUTCOME_RANK[o])
    deciding = [r for r in results if r.status is winning_outcome] or results
    confidence = sum(r.confidence for r in deciding) / len(deciding)

    return Analysis(
        outcome=winning_outcome,
        summary=summary
        or f"{len(deciding)}/{len(results)} payloads returned {winning_outcome.value}",
        detail="; ".join(r.notes for r in deciding if r.notes),
        confidence=round(confidence, 4),
        evidence={
            "count": len(results),
            "results": [r.to_dict() for r in results],
        },
    )


def pick_recommendation(results: list[AttackResult]) -> Recommendation | None:
    """Pick the recommendation to surface for a folded set of results.

    Prefers a recommendation attached to the highest-ranked outcome present (a FAIL's advice
    matters more than a PASS's), then the first non-``None`` recommendation found at that rank.
    Returns ``None`` if no result carries one -- callers should fall back to their own default
    recommendation in that case, since the engine requires ``recommendation()`` to always return
    something.
    """
    if not results:
        return None

    for rank in (
        PluginOutcome.FAIL,
        PluginOutcome.ERROR,
        PluginOutcome.PASS,
        PluginOutcome.SKIPPED,
    ):
        candidates = [r.recommendation for r in results if r.status is rank and r.recommendation]
        if candidates:
            return candidates[0]
    return None


__all__ = ["ResultBuilder", "fold_results", "pick_recommendation"]
