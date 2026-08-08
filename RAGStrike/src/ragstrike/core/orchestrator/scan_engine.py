"""``ScanEngine`` -- the scan lifecycle, and the single entry point into the framework.

    authorize -> discover plugins -> negotiate capabilities -> plan -> execute -> collect -> store

The CLI calls this. The API will call this. Neither reimplements any of it, and neither is allowed
to contain a step that lives here.

**No attack logic.** The engine sequences; it does not decide anything about security. That is the
whole point of the phase: this is the Burp Suite engine before any scanner exists, and it works
correctly with zero real plugins installed.

The engine depends on ports, never on implementations. The adapter arrives as a
``TargetAdapter``; persistence arrives as repositories. Wiring happens at the composition root
(``cli/main.py``), which is the only module that knows every concrete class.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
import logging

from ragstrike.analyzers.base.finding import Finding
from ragstrike.analyzers.base.observation import Observation
from ragstrike.analyzers.engine import AnalyzerEngine
from ragstrike.core.config.models import Settings
from ragstrike.core.contracts.repositories import (
    FindingRepositoryPort,
    ScanRepositoryPort,
    TargetRepositoryPort,
)
from ragstrike.core.contracts.target_adapter import TargetAdapter
from ragstrike.core.errors import AuthorizationError, RAGStrikeError, TargetUnreachableError
from ragstrike.models.entities.scan import PluginResult, ScanSession
from ragstrike.models.entities.target import Target
from ragstrike.models.values.enums import ScanState
from ragstrike.plugins.registry.plugin_registry import PluginHealth, PluginRegistry
from ragstrike.scheduler.scan_scheduler import (
    PlanCallback,
    ProfileSelector,
    ProgressCallback,
    ScanPlan,
    ScanScheduler,
)

log = logging.getLogger(__name__)


@dataclass(slots=True)
class ScanOutcome:
    """Everything one scan produced."""

    session: ScanSession
    results: list[PluginResult]
    plugin_health: PluginHealth
    plan: ScanPlan
    #: Standardised findings, when an analyzer was supplied. Empty otherwise -- and empty is not the
    #: same as "nothing found", which is why the engine records which of the two happened.
    findings: list[Finding] = field(default_factory=list)
    #: False when no analyzer was wired in, so a caller can tell "no findings" from "not analysed".
    analyzed: bool = False

    @property
    def has_failures(self) -> bool:
        """Whether any plugin found the target vulnerable."""
        return self.session.plugins_failed > 0



def _apply_payload_tiers(plan: object, profile: object) -> None:
    """Push the profile's ``payload_tiers`` into every runnable plugin's config.

    WHY THIS EXISTS
        Profiles declare ``payload_tiers`` -- "how deep to go within each pack" -- and it was parsed,
        validated, shown by `ragstrike profiles`, and returned over the API, but **never reached a
        plugin**. The packs read their depth from a config key named ``tiers`` and defaulted to
        ``["quick", "standard"]``, so every profile ran the same depth regardless of what it said.

        The visible symptom: `--profile quick` declares ``payload_tiers: ["quick"]`` and ran 17
        prompt-injection payloads instead of 4, because the pack fell back to its own default. So
        "quick" took as long as "standard" on the packs they share, and `smoke` could never be made
        genuinely fast.

        Two names for one idea is what caused it: the profile says ``payload_tiers``, the plugin
        contract says ``tiers``. The translation happens here, once, at the point where the profile
        and the loaded plugins first meet.

    Written defensively -- an unknown plan shape or a profile without tiers is a no-op rather than a
    crash, because a scan must not fail over a depth hint.
    """
    tiers = list(getattr(profile, "payload_tiers", ()) or ())
    if not tiers:
        return
    for plugin in getattr(plan, "runnable", ()) or ():
        # `LoadedPlugin` holds the manifest and the attack instance; the PluginContext -- and its
        # mutable config dict -- lives on the attack. Reaching for `plugin.context` silently found
        # nothing and the whole translation was a no-op, which is exactly the shape of the bug this
        # function exists to fix, so it is worth being explicit about the path.
        config = getattr(getattr(plugin, "attack", None), "context", None)
        config = getattr(config, "config", None)
        if isinstance(config, dict):
            config["tiers"] = tiers


class ScanEngine:
    """Runs the complete scan lifecycle."""

    def __init__(
        self,
        *,
        settings: Settings,
        registry: PluginRegistry,
        scheduler: ScanScheduler,
        scan_repository: ScanRepositoryPort,
        target_repository: TargetRepositoryPort,
        engine_version: str,
        analyzer: AnalyzerEngine | None = None,
        finding_repository: FindingRepositoryPort | None = None,
    ) -> None:
        self.settings = settings
        self.registry = registry
        self.scheduler = scheduler
        self.scans = scan_repository
        self.targets = target_repository
        self.engine_version = engine_version
        #: Optional. Without it a scan produces raw plugin results and no findings -- which is
        #: exactly what happened for thirteen phases: the analyzer was built, the reporting engine
        #: was built, and nothing joined the two, so the findings table stayed empty and every
        #: report had a risk score of zero.
        self.analyzer = analyzer
        self.findings = finding_repository

    async def run(
        self,
        *,
        target: Target,
        adapter: TargetAdapter,
        profile: ProfileSelector | None = None,
        scan_id: str | None = None,
        name: str = "",
        on_plan: PlanCallback | None = None,
        on_result: ProgressCallback | None = None,
    ) -> ScanOutcome:
        """Execute one scan against *target*.

        A *profile* narrows which packs run. Anything it excludes is reported as a skip with a
        reason, never dropped -- see :meth:`ScanScheduler.plan`.

        *scan_id* lets the caller choose the identifier. The API needs this: ``POST /scans`` must
        return an id **before** the engine has created its session, and an id the client cannot then
        query is worse than no id at all. Omitted, the engine mints one as before.

        *name* is an operator label stored with the session. Without one a scan is identifiable only
        by a 32-character hex id, which is unreadable at a glance and identical in shape to every
        other scan in the list.

        *on_plan* fires once, with the total number of plugins, as soon as planning finishes. Without
        it a progress endpoint has a numerator and no denominator for the whole scan, and reports 0%
        from start to finish.

        Raises:
            AuthorizationError: No authorization record, and ``safety.require_authorization`` is on.
            TargetUnreachableError: The target failed its health check.
        """
        self._assert_authorized(target)

        stored_target = await self.targets.upsert(target)
        session = ScanSession(
            id=scan_id or ScanSession.new_id(),
            target_id=stored_target.id,
            target_name=stored_target.name,
            name=name,
            # Recorded so a listing can distinguish a FAIL at 22% coverage from a FAIL at 100%.
            #
            # `id` first, `name` as a fallback. The CLI hands this a `ScanProfile` whose `name` is
            # the display label ("Smoke test") while its `id` is what the operator typed
            # (`--profile smoke`) and what `configs/profiles/` calls the file. Reading `name` first
            # stored the label, so a column read "Smoke test" beside a command that says `smoke`.
            #
            # Resolved HERE rather than in each caller because both the CLI and the API reach the
            # engine by different paths, and fixing one of them is how they drift apart.
            profile=getattr(profile, "id", "") or getattr(profile, "name", "") or "",
            state=ScanState.QUEUED,
            engine_version=self.engine_version,
        )
        await self.scans.create(session, config_snapshot=self.settings.snapshot())
        log.info(
            "scan started",
            extra={
                "scan_id": session.id,
                "target": stored_target.name,
                "adapter": stored_target.adapter,
                "url": stored_target.url,
            },
        )

        try:
            plan = await self._prepare(session, adapter, profile)
            if on_plan is not None:
                # The runnable set, not `plan.total`. Skipped packs resolve instantly and would
                # otherwise fill most of a progress bar before the scan had done anything.
                on_plan(len(plan.runnable))
            results = await self._execute(session, plan, adapter, on_result)
        except asyncio.CancelledError:
            # CancelledError derives from BaseException, not Exception, so neither handler below
            # caught it. A cancelled scan therefore left its row in PREPARING or RUNNING forever --
            # and a scan stuck in RUNNING reads, months later, as one that is still going.
            #
            # `shield` is required: the surrounding task is already being cancelled, so an
            # unshielded await would be cancelled too and the write would never land.
            await asyncio.shield(self._terminate(session, ScanState.CANCELLED, "cancelled"))
            raise
        except RAGStrikeError as exc:
            await self._fail(session, f"{exc.code}: {exc.message}")
            raise
        except Exception as exc:
            await self._fail(session, f"{type(exc).__name__}: {exc}")
            raise

        findings = await self._analyze(session, plan, results)

        session.state = ScanState.COMPLETED
        session.finished_at = datetime.now(UTC)
        await self.scans.update(session)

        log.info(
            "scan finished",
            extra={
                "scan_id": session.id,
                "state": session.state.value,
                "executed": session.plugins_executed,
                "passed": session.plugins_passed,
                "failed": session.plugins_failed,
                "errored": session.plugins_errored,
                "skipped": session.plugins_skipped,
                "coverage": round(session.coverage, 3),
                "elapsed_ms": session.elapsed_ms,
            },
        )
        return ScanOutcome(
            session=session,
            results=results,
            plugin_health=self.registry.health,
            plan=plan,
            findings=findings,
            analyzed=self.analyzer is not None,
        )

    # -- lifecycle steps ----------------------------------------------------------------------

    async def _prepare(
        self,
        session: ScanSession,
        adapter: TargetAdapter,
        profile: ProfileSelector | None = None,
    ) -> ScanPlan:
        """Discover plugins, confirm the target answers, and build the plan."""
        session.state = ScanState.PREPARING
        await self.scans.update(session)

        health = self.registry.discover()
        session.plugin_inventory = health.inventory

        probe = await adapter.health_check()
        if not probe.reachable:
            raise TargetUnreachableError(
                f"{session.target_name!r} is not reachable: {probe.detail}",
                hint="Start the target, or correct its url in configs/targets.yaml.",
            )
        log.info(
            "target reachable",
            extra={
                "scan_id": session.id,
                "latency_ms": probe.latency_ms,
                "detail": probe.detail,
            },
        )

        descriptor = adapter.describe()
        plan = self.scheduler.plan(health.active, descriptor.capabilities, profile=profile)
        _apply_payload_tiers(plan, profile)
        session.plugins_total = plan.total
        await self.scans.update(session)
        return plan

    async def _execute(
        self,
        session: ScanSession,
        plan: ScanPlan,
        adapter: TargetAdapter,
        on_result: ProgressCallback | None,
    ) -> list[PluginResult]:
        """Run the plan, folding each result into the session counters as it arrives."""
        session.state = ScanState.RUNNING
        await self.scans.update(session)

        def record(result: PluginResult) -> None:
            session.record(result.outcome)
            if on_result:
                on_result(result)

        results = await self.scheduler.run(
            scan_id=session.id, plan=plan, target=adapter, on_result=record
        )
        await self.scans.add_results(results)
        return results

    async def _analyze(
        self, session: ScanSession, plan: ScanPlan, results: list[PluginResult]
    ) -> list[Finding]:
        """Turn raw plugin results into standardised findings, and store them.

        **This is the step that was missing.** ``analyzers/`` shipped in Phase 10 and ``reporters/``
        in Phase 11, but nothing ever converted a ``PluginResult`` into an ``Observation``, so the
        findings table stayed empty, every report scored 0.0, and the dashboard rendered a grade of
        "?" for scans that had run perfectly well.

        Returns an empty list when no analyzer was supplied. The caller distinguishes that from
        "analysed and found nothing" through ``ScanOutcome.analyzed`` -- the same PASS versus
        INCONCLUSIVE distinction this project applies everywhere else, at the level of the scan.

        Failure here is logged and swallowed. The scan itself succeeded; losing its raw results
        because the analysis stage tripped would discard the expensive half of the work to protect
        the cheap half.
        """
        if self.analyzer is None:
            return []

        session.state = ScanState.ANALYZING
        await self.scans.update(session)

        # Category comes from the plugin manifest, not from the result: the analyzer selects
        # category-scoped rules with it, and a result carries only its slug.
        categories = {plugin.slug: plugin.metadata().category for plugin in plan.runnable}
        categories.update({plugin.slug: plugin.metadata().category for plugin, _ in plan.skipped})

        try:
            observations = [
                Observation.from_plugin_result(
                    result,
                    category=categories.get(result.plugin_slug, ""),
                    target=session.target_name,
                )
                for result in results
            ]
            report = self.analyzer.analyze(observations, scan_id=session.id)
        except Exception:
            log.exception("analysis failed", extra={"scan_id": session.id})
            return []

        if self.findings is not None and report.findings:
            try:
                await self.findings.add_findings(list(report.findings))
            except Exception:
                log.exception("could not persist findings", extra={"scan_id": session.id})

        log.info(
            "scan analysed",
            extra={
                "scan_id": session.id,
                "findings": len(report.findings),
                "vulnerabilities": len(report.vulnerabilities),
            },
        )
        return list(report.findings)

    async def _fail(self, session: ScanSession, error: str) -> None:
        """Mark the session failed and persist it.

        A scan that crashed must leave a record saying so. Silence is indistinguishable from a scan
        that was never started, and that ambiguity is exactly what makes a scanner untrustworthy.
        """
        await self._terminate(session, ScanState.FAILED, error)
        log.error("scan failed", extra={"scan_id": session.id, "error": error})

    async def _terminate(self, session: ScanSession, state: ScanState, error: str) -> None:
        """Move *session* to a terminal state and persist it.

        Every exit path goes through here, so no path can leave a row in a running state. The write
        failing is logged and swallowed: the scan is already ending, and raising here would replace
        the real reason with a database error.
        """
        session.state = state
        session.finished_at = datetime.now(UTC)
        session.error = error
        try:
            await self.scans.update(session)
        except Exception:
            log.exception(
                "could not persist terminal scan state",
                extra={"scan_id": session.id, "state": state.value},
            )

    def _assert_authorized(self, target: Target) -> None:
        """Refuse to start without an authorization record.

        A required field on the target, not a checkbox in a UI, and it is carried into every result
        so a report always says who authorized the testing that produced it (ADR-017).
        """
        if not self.settings.safety.require_authorization:
            log.warning(
                "authorization check disabled",
                extra={"target": target.name},
            )
            return

        if not target.is_authorized:
            raise AuthorizationError(
                f"Target {target.name!r} has no authorization record.",
                hint=(
                    "Add an authorization block (authorized_by, authorization_ref) to the target "
                    "in configs/targets.yaml. Only scan systems you are authorized to test."
                ),
            )
