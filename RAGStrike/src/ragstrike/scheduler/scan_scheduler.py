"""``ScanScheduler`` -- decides what runs, then runs it.

Phase 3 executes plugins **sequentially**. Concurrency is designed for and deliberately not
implemented: the seams are here (a semaphore around ``_run_one``, a rate limiter before each probe),
but a sequential engine is far easier to reason about while the contracts are still settling, and
the bottleneck in a real scan is the target's inference throughput rather than this loop.

The scheduler never imports ``target_adapters`` or ``database`` -- an import-linter contract enforces
that. It receives a ``TargetAdapter`` typed by the port and hands it to plugins. That is what lets
the whole scheduling path be tested with a fake target and no network at all.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
import logging
import time
from typing import Protocol

from ragstrike.core.contracts.target_adapter import TargetAdapter
from ragstrike.models.entities.scan import PluginResult
from ragstrike.models.values.enums import Capability, PluginOutcome
from ragstrike.plugins.events import EventBus, NoOpBus, PluginEvent, PluginEventType
from ragstrike.plugins.registry.plugin_registry import LoadedPlugin

log = logging.getLogger(__name__)

#: Called after each plugin finishes, so the CLI can render progress without the scheduler knowing
#: what a terminal is.
ProgressCallback = Callable[[PluginResult], None]

#: Called once, with the total number of planned plugins, as soon as planning finishes. A
#: progress display needs the denominator before the first result arrives, not after the last.
PlanCallback = Callable[[int], None]


class ProfileSelector(Protocol):
    """The one thing the scheduler needs from a scan profile.

    ``ScanProfile`` lives in ``core.config`` and the layer contract forbids importing it here. It
    satisfies this protocol structurally, so profile-aware planning costs no coupling at all.
    """

    def selects(self, slug: str) -> bool:
        """Whether the plugin with *slug* is in scope for this scan."""
        ...

    def requested_packs(self) -> list[str]:
        """Every slug this profile asked for. Empty means "everything installed".

        Needed so the planner can notice a profile asking for a pack that **is not installed**.
        Without it such a pack is invisible: it is not in the plugin list, so it is never skipped,
        never counted, and never reported -- which is exactly how ``quick.yaml`` came to name four
        packs, run two, and say nothing about the difference.
        """
        ...


@dataclass(slots=True)
class ScanPlan:
    """What the scheduler decided to do, before it does any of it.

    Built separately from execution so it can be inspected, printed, or asserted on in a test
    without a target being involved. ``skipped`` is a first-class part of the plan: a scan that
    could only run half its plugins must never render the same as one that ran them all.
    """

    runnable: list[LoadedPlugin] = field(default_factory=list)
    skipped: list[tuple[LoadedPlugin, str]] = field(default_factory=list)
    #: Slugs the profile asked for that are not installed. Separate from ``skipped`` because there
    #: is no ``LoadedPlugin`` to attach -- the pack does not exist. Reported, never counted as
    #: covered: a profile asking for a pack nobody built is a coverage gap, not a plan item.
    missing: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.runnable) + len(self.skipped)


class ScanScheduler:
    """Plans and runs the plugin set for one scan."""

    def __init__(self, *, max_concurrency: int = 1, event_bus: EventBus | None = None) -> None:
        #: Honoured from configuration but not yet acted on -- see the module docstring.
        self.max_concurrency = max_concurrency
        #: Publishes plugin lifecycle events. Defaults to a no-op bus so callers that do not care
        #: never have to construct one.
        self.events: EventBus = event_bus or NoOpBus()

    # -- planning -----------------------------------------------------------------------------

    def plan(
        self,
        plugins: list[LoadedPlugin],
        capabilities: tuple[Capability, ...],
        *,
        profile: ProfileSelector | None = None,
    ) -> ScanPlan:
        """Decide which plugins can run against a target with *capabilities*.

        Pure: no I/O, no target contact. That is what makes it exhaustively testable, and scheduling
        bugs matter precisely because they are invisible in the output -- a whole plugin silently
        unscheduled looks exactly like a plugin that found nothing.

        A *profile* narrows the set by slug. **Out of profile is a recorded skip, not a silent
        omission** -- it lands in ``plan.skipped`` with a reason and therefore in the report's
        coverage section, so a quick scan can never be mistaken for a full one (ADR-020).

        A profile naming a pack that is **not installed** lands in ``plan.missing``. That case used
        to vanish entirely: the pack is absent from the plugin list, so nothing iterated over it and
        nothing reported it. ``quick.yaml`` named four packs, two of which were never built, and ran
        two -- with no line anywhere saying so.

        Typed as a narrow :class:`ProfileSelector` protocol rather than as ``ScanProfile`` because
        the scheduler needs one predicate, not a configuration object, and the layer contract keeps
        ``scheduler`` from importing ``core.config``.
        """
        plan = ScanPlan()
        installed = {plugin.slug for plugin in plugins}
        if profile is not None:
            plan.missing = sorted(
                slug for slug in profile.requested_packs() if slug not in installed
            )

        for plugin in plugins:
            if profile is not None and not profile.selects(plugin.slug):
                plan.skipped.append((plugin, "not selected by the active scan profile"))
                continue
            if plugin.attack.applies_to(capabilities):
                plan.runnable.append(plugin)
            else:
                required = ", ".join(c.value for c in plugin.metadata().requires_capabilities)
                plan.skipped.append((plugin, f"target does not support: {required}"))

        if plan.missing:
            log.warning(
                "scan profile names packs that are not installed",
                extra={"missing": plan.missing},
            )

        log.info(
            "scan planned",
            extra={
                "runnable": len(plan.runnable),
                "skipped": len(plan.skipped),
                "missing": len(plan.missing),
                "capabilities": [c.value for c in capabilities] or ["unverified"],
            },
        )
        return plan

    # -- execution ----------------------------------------------------------------------------

    async def run(
        self,
        *,
        scan_id: str,
        plan: ScanPlan,
        target: TargetAdapter,
        on_result: ProgressCallback | None = None,
    ) -> list[PluginResult]:
        """Execute *plan* against *target* and collect the results.

        One plugin at a time. Every plugin is isolated: an unexpected exception becomes an ``ERROR``
        result and the scan continues. One broken plugin must never lose the other nineteen.
        """
        results: list[PluginResult] = []

        for plugin, reason in plan.skipped:
            result = PluginResult(
                id=PluginResult.new_id(),
                scan_id=scan_id,
                plugin_slug=plugin.slug,
                plugin_version=plugin.version,
                outcome=PluginOutcome.SKIPPED,
                summary=reason,
            )
            results.append(result)
            if on_result:
                on_result(result)

        for plugin in plan.runnable:
            result = await self._run_one(scan_id=scan_id, plugin=plugin, target=target)
            results.append(result)
            if on_result:
                on_result(result)

        return results

    async def _run_one(
        self, *, scan_id: str, plugin: LoadedPlugin, target: TargetAdapter
    ) -> PluginResult:
        """Run one plugin end to end through the Phase 4 lifecycle.

        Order (also in ``docs/plugin-lifecycle.md``)::

            healthcheck  -> if unhealthy, SKIPPED with the failing rule's detail.
            setup        -> once, before any payloads.
            payloads     -> deterministic; ordering matters for reproducibility.
            execute      -> the only step that does I/O.
            analyze      -> pure.
            recommendation
            cleanup      -> ALWAYS runs, even on error, in a finally block.

        This is the isolation boundary. When concurrency arrives it wraps this call in a
        semaphore; nothing inside changes.
        """
        started = time.perf_counter()
        attack = plugin.attack
        self._publish(PluginEventType.STARTED, scan_id, plugin)

        def elapsed() -> int:
            return int((time.perf_counter() - started) * 1000)

        # -- healthcheck: SKIPPED here is a coverage-gap outcome, not a failure --------
        try:
            health = attack.healthcheck()
        except Exception as exc:
            log.exception(
                "plugin healthcheck errored",
                extra={"scan_id": scan_id, "slug": plugin.slug},
            )
            self._publish(PluginEventType.FAILED, scan_id, plugin, error=str(exc))
            return _errored(plugin, scan_id, exc, elapsed())

        if not health.healthy:
            detail = "; ".join(check.detail or check.rule for check in health.failed_checks)
            log.info(
                "plugin skipped by healthcheck",
                extra={"scan_id": scan_id, "slug": plugin.slug, "detail": detail},
            )
            self._publish(
                PluginEventType.FINISHED, scan_id, plugin, outcome=PluginOutcome.SKIPPED.value
            )
            return PluginResult(
                id=PluginResult.new_id(),
                scan_id=scan_id,
                plugin_slug=plugin.slug,
                plugin_version=plugin.version,
                outcome=PluginOutcome.SKIPPED,
                summary=f"healthcheck refused: {detail}",
                elapsed_ms=elapsed(),
            )

        # -- setup -> execute -> analyze -> recommendation, cleanup always -------------
        try:
            attack.setup()
            try:
                payloads = attack.payloads()
                log.info(
                    "plugin executing",
                    extra={
                        "scan_id": scan_id,
                        "slug": plugin.slug,
                        "payloads": len(payloads),
                    },
                )

                records = await attack.execute(target, payloads)
                analysis = attack.analyze(records)
                recommendation = attack.recommendation(analysis)

                result = PluginResult(
                    id=PluginResult.new_id(),
                    scan_id=scan_id,
                    plugin_slug=plugin.slug,
                    plugin_version=plugin.version,
                    outcome=analysis.outcome,
                    summary=analysis.summary,
                    detail=analysis.detail,
                    recommendation=recommendation.title,
                    payloads_executed=len(records),
                    elapsed_ms=elapsed(),
                    evidence=analysis.evidence,
                )
                log.info(
                    "plugin executed",
                    extra={
                        "scan_id": scan_id,
                        "slug": plugin.slug,
                        "outcome": result.outcome.value,
                        "elapsed_ms": result.elapsed_ms,
                    },
                )
                self._publish(
                    PluginEventType.FINISHED, scan_id, plugin, outcome=result.outcome.value
                )
                return result
            finally:
                # Cleanup ALWAYS runs. Errors here are logged and swallowed -- a leaking cleanup
                # must not turn a successful scan into an errored one, and a per-cleanup failure
                # is a plugin bug that gets reported through the log, not the outcome.
                try:
                    attack.cleanup()
                except Exception:
                    log.exception(
                        "plugin cleanup errored",
                        extra={"scan_id": scan_id, "slug": plugin.slug},
                    )

        except asyncio.CancelledError:
            # Cancellation is a control-flow signal, not a plugin failure. Never swallow it.
            raise
        except Exception as exc:
            log.exception("plugin errored", extra={"scan_id": scan_id, "slug": plugin.slug})
            self._publish(PluginEventType.FAILED, scan_id, plugin, error=str(exc))
            return _errored(plugin, scan_id, exc, elapsed())

    def _publish(
        self,
        event: PluginEventType,
        scan_id: str,
        plugin: LoadedPlugin,
        **payload: object,
    ) -> None:
        self.events.publish(
            PluginEvent(
                type=event,
                plugin_slug=plugin.slug,
                scan_id=scan_id,
                payload=dict(payload),
            )
        )


def _errored(
    plugin: LoadedPlugin, scan_id: str, exc: BaseException, elapsed_ms: int
) -> PluginResult:
    return PluginResult(
        id=PluginResult.new_id(),
        scan_id=scan_id,
        plugin_slug=plugin.slug,
        plugin_version=plugin.version,
        outcome=PluginOutcome.ERROR,
        summary=f"{type(exc).__name__}: {exc}",
        elapsed_ms=elapsed_ms,
        error=f"{type(exc).__name__}: {exc}",
    )
