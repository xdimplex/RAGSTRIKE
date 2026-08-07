"""DummyAttack -- validates the extended plugin lifecycle without attacking anything.

The reference implementation of :class:`~ragstrike.plugins.base.attack.BaseAttack` and the
template to copy when writing a real attack pack. Implements the full Phase 4 lifecycle -- setup,
healthcheck, validate, cleanup all present -- and **always returns PASS**.

It contains no attack logic, deliberately. Phase 4 built the plugin framework; the framework has
to be provable before there is anything to prove it with, and validating a framework only with a
working exploit means discovering the framework's failure modes later, in the dark.

To write a real pack: copy this directory, change the slug in ``metadata.yaml``, put actual
payloads in :meth:`payloads`, and a real verdict in :meth:`analyze`. **Nothing in the engine
changes.**
"""

from __future__ import annotations

import time

from ragstrike.core.contracts.target_adapter import TargetAdapter, TargetRequest, TargetResponse
from ragstrike.models.values.enums import Capability, PluginOutcome, Severity
from ragstrike.plugins.base.attack import (
    Analysis,
    BaseAttack,
    ExecutionRecord,
    Payload,
    Recommendation,
)
from ragstrike.plugins.base.reports import Check, HealthReport, ValidationReport


class DummyAttack(BaseAttack):
    """A no-op plugin that exercises every step of the lifecycle.

    Declarative style: identity lives in the class attributes, so ``metadata()`` is derived and
    does not need to be overridden. That is what makes the file short.
    """

    # -- declarative identity ------------------------------------------------------
    plugin_id = "dummy-attack"
    plugin_name = "Dummy Attack"
    plugin_version = "1.0.1"
    author = "RAGStrike"
    description = (
        "Validates the scan lifecycle end to end. Sends one benign question and always "
        "reports PASS. Tests nothing about security."
    )
    category = "diagnostic"
    severity = Severity.INFO
    requires_capabilities = (Capability.CHAT,)
    tags = ("diagnostic", "reference")
    references = ("docs/plugin-development.md",)
    license = "Apache-2.0"

    # -- lifecycle ------------------------------------------------------------------

    def validate(self) -> ValidationReport:
        """Runs at load time. Combined with the framework-level rules by the registry.

        The base class already checks for a slug, a non-zero version, and at least one
        capability. This plugin adds one rule of its own: its configured question must be
        non-empty. A real pack's ``validate`` would check its payload set, its detector
        wiring, and any pack-specific invariants.
        """
        base = super().validate()
        question = str(self.context.config.get("question", "")).strip()
        return base.merge(
            ValidationReport(
                checks=[
                    Check(
                        rule="question-non-empty",
                        passed=bool(question),
                        detail="" if question else "options.question must not be empty.",
                    )
                ]
            )
        )

    def healthcheck(self) -> HealthReport:
        """Runs before each scan. Reports healthy unconditionally.

        A real pack whose detectors need a canary would report healthy only when the target
        confirms an ingest capability -- so that plugin is SKIPPED against chat-only targets
        rather than running and failing halfway.
        """
        return HealthReport(checks=[Check(rule="always-healthy", passed=True)])

    def setup(self) -> None:
        """No-op. Real packs would allocate resources here."""
        self.context.logger.debug("dummy setup")

    def cleanup(self) -> None:
        """No-op. Real packs would release resources here -- and this is where canary cleanup
        will land in the analyzer phase."""
        self.context.logger.debug("dummy cleanup")

    # -- required behavioural methods ---------------------------------------------

    def payloads(self) -> list[Payload]:
        """One harmless question.

        Deterministic, as the contract requires: the same options always produce the same
        payload in the same position, so results stay comparable between runs.

        A pack whose payloads live on disk would replace this body with
        ``return self.load_payloads()``.
        """
        question = str(self.context.config.get("question", "Hello. Are you working?"))
        return [
            Payload(
                id="dummy-001",
                content=question,
                tier="quick",
                description="Benign connectivity probe.",
            )
        ]

    async def execute(
        self, target: TargetAdapter, payloads: list[Payload]
    ) -> list[ExecutionRecord]:
        """Send each payload and record what came back.

        The only method here that performs I/O. Note that a failing payload is captured as a
        record carrying ``error`` rather than raised -- one bad payload must never lose the
        others.
        """
        records: list[ExecutionRecord] = []

        for payload in payloads:
            started = time.perf_counter()
            try:
                response = await target.chat(TargetRequest(prompt=payload.content))
                records.append(
                    ExecutionRecord(
                        payload_id=payload.id,
                        prompt=payload.content,
                        response=response,
                        elapsed_ms=int((time.perf_counter() - started) * 1000),
                        error=response.error,
                    )
                )
            except Exception as exc:
                records.append(
                    ExecutionRecord(
                        payload_id=payload.id,
                        prompt=payload.content,
                        response=TargetResponse(text="", error=str(exc)),
                        elapsed_ms=int((time.perf_counter() - started) * 1000),
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )

        return records

    def analyze(self, records: list[ExecutionRecord]) -> Analysis:
        """Always PASS.

        Pure, as the contract requires: no network, no clock, no randomness. Given the same
        records it returns the same analysis on any machine, which is what will let Phase 5's
        replay harness re-run analysis offline over stored evidence.

        A real plugin decides ``PASS`` or ``FAIL`` here. This one reports the target resisted,
        because it never attacked it.
        """
        answered = [r for r in records if r.ok and r.response.text.strip()]

        return Analysis(
            outcome=PluginOutcome.PASS,
            summary=(
                f"lifecycle OK — {len(answered)}/{len(records)} payloads answered"
                if records
                else "lifecycle OK — no payloads"
            ),
            detail=(
                "This plugin validates that the framework can plan, execute, analyze, and "
                "store a result. It performs no security testing, so PASS here means the "
                "framework works, not that the target is secure."
            ),
            confidence=1.0,
            evidence={
                "payloads_sent": len(records),
                "responses_received": len(answered),
                "first_response_chars": len(records[0].response.text) if records else 0,
                "transport_errors": [r.error for r in records if r.error],
            },
        )

    def recommendation(self, analysis: Analysis) -> Recommendation:
        """Advice for *analysis*.

        A real pack varies its guidance by outcome, which is why the analysis is passed in
        rather than the recommendation being a constant. This one only ever produces PASS, so
        the branch exists to show the shape.
        """
        if analysis.outcome is PluginOutcome.PASS:
            remediation = (
                "This plugin is a diagnostic. It confirms the scan lifecycle runs; it does not "
                "assess security. Install real attack packs to get findings."
            )
        else:
            remediation = (
                "This plugin could not complete its probe. Check target reachability and the "
                "adapter configuration in configs/targets.yaml."
            )

        return Recommendation(
            title="No action required",
            remediation=remediation,
            references=("docs/annex-b-attack-catalog.md",),
            effort="LOW",
        )
