"""``EvaluationAttack`` -- the base class for non-offensive evaluation plugins.

An *evaluation* plugin asks whether a documented security behaviour actually holds. It is not an
exploit: it sends benign prompts, reads the answers, and compares what it observed against what the
test case said to expect. Nothing it does changes the target.

**Why this exists rather than five copies of the same file.** Phase 6's five evaluation plugins
share an identical ``payloads()`` (read the test cases from ``payloads/``) and an identical
``execute()`` (send each one, record what came back). Only the success criterion differs -- which is
exactly the thing the Phase 5 SDK promised a plugin author would be left writing. Hoisting the
shared half here is that promise applied to the first real plugins: a subclass implements
:meth:`judge` and :meth:`recommendation`, and nothing else.

**Added in Phase 6, additive only.** No Phase 5 module changed to accommodate it; this is a new
optional convenience built entirely on the existing SDK pieces. Plugins that want the raw
``BaseAttack`` contract still have it, unchanged -- ``examples/custom_pack/plugin.py`` continues to
use it directly and is the reference for that style.

**Read-only by construction.** The only target operation reachable from here is
:meth:`TargetAdapter.chat`, which the adapter contract defines as a question-and-answer exchange.
There is no ingest, no delete, no upload on this path, so "never modifies the target" is a property
of what the contract exposes rather than a rule a plugin author has to remember.
"""

from __future__ import annotations

import abc
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ragstrike.core.contracts.target_adapter import TargetAdapter, TargetResponse
from ragstrike.models.values.enums import PluginOutcome
from ragstrike.plugins.base.attack import Analysis, BaseAttack, ExecutionRecord, Payload
from ragstrike.sdk.payload_loader import SdkPayloadLoader
from ragstrike.sdk.request_builder import TargetRequestBuilder
from ragstrike.sdk.response_parser import ResponseParser
from ragstrike.sdk.result_builder import ResultBuilder, fold_results


@dataclass(frozen=True, slots=True)
class Verdict:
    """One test case's judgement, as returned by :meth:`EvaluationAttack.judge`.

    Attributes:
        outcome: ``PASS`` if the expected behaviour held, ``FAIL`` if it demonstrably did not, and
            ``INCONCLUSIVE`` when the answer does not settle it either way. Returning
            ``INCONCLUSIVE`` is the honest result for a model that declined to answer or replied
            with something the criterion cannot classify -- it is not a failure to write a better
            criterion, and rounding it to ``PASS`` would report resistance nobody observed.
        note: One line of human-readable justification, carried into the evidence. Say what was
            observed, not what it means -- the outcome already carries the meaning.
        confidence: ``0.0``-``1.0``. Leave at ``1.0`` for a deterministic criterion (a substring
            that is either present or not); lower it when the criterion is a heuristic.
    """

    outcome: PluginOutcome
    note: str = ""
    confidence: float = 1.0

    @classmethod
    def passed(cls, note: str = "", *, confidence: float = 1.0) -> Verdict:
        return cls(PluginOutcome.PASS, note, confidence)

    @classmethod
    def failed(cls, note: str = "", *, confidence: float = 1.0) -> Verdict:
        return cls(PluginOutcome.FAIL, note, confidence)

    @classmethod
    def inconclusive(cls, note: str = "", *, confidence: float = 0.5) -> Verdict:
        """Default confidence is deliberately ``0.5``: an undetermined result should not average
        into a scan-level score as though it were a firm observation."""
        return cls(PluginOutcome.INCONCLUSIVE, note, confidence)


class EvaluationAttack(BaseAttack):
    """A plugin that checks an expected security behaviour and reports PASS/FAIL/INCONCLUSIVE.

    A subclass writes two methods::

        class MyEvaluation(EvaluationAttack):
            plugin_id = "my-evaluation"
            plugin_name = "My Evaluation"
            plugin_version = "1.0.0"
            category = "evaluation"

            def judge(self, observed, expects):
                if expects.get("must_refuse") and "cannot" in observed.text().lower():
                    return Verdict.passed("target declined, as expected")
                return Verdict.failed("target complied with the instruction")

            def recommendation(self, analysis):
                return Recommendation(title="...", remediation="...")

    Everything else -- loading the test cases, sending them, timing them, catching per-payload
    transport failures, building standardized results, folding them into one ``Analysis`` -- is
    inherited.
    """

    #: Set by :meth:`execute` so :meth:`analyze` can reach each payload's ``expects`` block.
    #: ``analyze`` receives only records, and a record carries its payload *id* rather than the
    #: payload, so the mapping has to be captured while both are in scope.
    _expectations: dict[str, dict[str, Any]]

    #: Captured in :meth:`execute` purely so results can name what they ran against. ``analyze``
    #: never receives the target, by design -- it must stay pure and re-runnable over stored
    #: evidence with nothing to connect to.
    _target_label: str

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._expectations = {}
        self._target_label = "unknown"

    # -- inherited halves -----------------------------------------------------------------------

    def payloads(self) -> list[Payload]:
        """Read the test cases from this plugin's ``payloads/`` directory.

        Lenient by design (:class:`SdkPayloadLoader`): one malformed case file is skipped and
        reported rather than taking the whole evaluation down with it.
        """
        return SdkPayloadLoader(self.context.payload_dir).all()

    async def execute(
        self, target: TargetAdapter, payloads: list[Payload]
    ) -> list[ExecutionRecord]:
        """Send every test case. The only method here that touches the network.

        A payload that raises is recorded as a failed record rather than propagating, so one
        unreachable moment does not discard the other cases' observations.
        """
        self._target_label = target.describe().url
        self._expectations = {p.id: dict(p.expects) for p in payloads}

        records: list[ExecutionRecord] = []
        for payload in payloads:
            request = TargetRequestBuilder().with_prompt(payload.content).build()
            try:
                response = await target.chat(request)
            except Exception as exc:
                response = TargetResponse(text="", error=f"{type(exc).__name__}: {exc}")
            records.append(
                ExecutionRecord(
                    payload_id=payload.id,
                    prompt=payload.content,
                    response=response,
                    elapsed_ms=getattr(response, "latency_ms", 0),
                    error=response.error,
                )
            )
        return records

    def analyze(self, records: list[ExecutionRecord]) -> Analysis:
        """Judge every record and fold the verdicts into one ``Analysis``.

        Pure: it calls :meth:`judge`, which is required to be pure too. Given the same records this
        returns the same analysis on any machine, which is what will let a replay harness re-run
        the criterion over stored evidence without contacting anything.
        """
        results = []
        for record in records:
            builder = ResultBuilder(
                plugin_name=self.plugin_name or type(self).__name__,
                target=self._target_label,
            ).from_execution_record(record)

            if record.error:
                # The transport failed, so there is nothing to judge. from_execution_record has
                # already marked this ERROR; saying anything about security here would be a guess.
                results.append(builder.with_notes(f"transport error: {record.error}").build())
                continue

            verdict = self.judge(
                ResponseParser(record.response),
                self._expectations.get(record.payload_id, {}),
            )
            results.append(
                builder.with_status(verdict.outcome)
                .with_confidence(verdict.confidence)
                .with_notes(verdict.note)
                .build()
            )

        return fold_results(results)

    # -- the half a subclass writes ---------------------------------------------------------------

    @abc.abstractmethod
    def judge(self, observed: ResponseParser, expects: Mapping[str, Any]) -> Verdict:
        """Decide whether one response met its test case's expectation.

        **Must be pure.** No network, no clock, no randomness -- it runs inside ``analyze``.

        Args:
            observed: The response, wrapped for extraction (``.text()``, ``.chunks()``,
                ``.sources()``, ``.citations()`` and friends).
            expects: The test case's ``expects`` block, verbatim from its YAML file. Empty when the
                case declared none.

        Returns:
            A :class:`Verdict`. Prefer :meth:`Verdict.inconclusive` over a guess.
        """


__all__ = ["EvaluationAttack", "Verdict"]
