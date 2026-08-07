"""Application services behind the routers.

WHY THE ROUTERS DO NOT CONTAIN THIS
    A router should translate HTTP into a call and a result back into HTTP. Everything here --
    building the engine, tracking a running scan, cancelling one -- is application logic that the
    CLI needs too and that must be testable without a web server.

WHY SCANS RUN IN THE BACKGROUND
    A scan is minutes to hours: every payload is a full round trip through a model. Holding an HTTP
    connection open for that is not an option, so ``POST /scans`` returns **202 Accepted** with an
    id, and the caller polls ``/progress`` or streams the SSE endpoint (ADR-014).

WHY THE RUNNING-SCAN REGISTRY IS IN PROCESS
    ADR-018: single-process asyncio. A scan is an ``asyncio.Task`` in this process, so cancellation
    is ``task.cancel()`` and progress is an object in memory. The moment a second process is
    introduced this becomes wrong -- and that is exactly the seam ADR-018 says to keep visible, so
    the constraint is stated here rather than discovered later.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
import logging
from typing import Any

from ragstrike import PLUGIN_API_VERSION, __version__
from ragstrike.analyzers.config import build_engine as build_analyzer
from ragstrike.core.config.loader import REPO_ROOT, load_settings, load_targets, select_target
from ragstrike.core.config.models import Settings
from ragstrike.core.config.profiles import ScanProfile, load_all_profiles, load_profile
from ragstrike.core.errors import RAGStrikeError
from ragstrike.core.orchestrator.scan_engine import ScanEngine
from ragstrike.database.connection import Database
from ragstrike.database.migrations.runner import run_migrations
from ragstrike.database.repositories.finding_repository import FindingRepository
from ragstrike.database.repositories.report_repository import ReportRepository
from ragstrike.database.repositories.scan_repository import ScanRepository
from ragstrike.database.repositories.target_repository import TargetRepository
from ragstrike.models.entities.scan import PluginResult, ScanSession
from ragstrike.models.values.enums import PluginOutcome, ScanState
from ragstrike.plugins.registry.plugin_manager import PluginManager
from ragstrike.plugins.registry.plugin_registry import PluginRegistry
from ragstrike.scheduler.scan_scheduler import ProfileSelector, ScanScheduler
from ragstrike.target_adapters.registry import build_adapter

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Selection:
    """An ad-hoc pack choice, layered on top of a profile.

    Satisfies the scheduler's ``ProfileSelector`` protocol structurally, so the planner needs no
    knowledge that a request rather than a file produced it.

    **Intersects with the profile rather than replacing it.** A profile is a depth policy; a
    selection is the operator narrowing within that policy. Letting a request widen past its profile
    would make ``--profile quick`` mean nothing once the dashboard was involved.
    """

    slugs: frozenset[str]
    profile: ScanProfile | None = None

    def selects(self, slug: str) -> bool:
        if self.profile is not None and not self.profile.selects(slug):
            return False
        return not self.slugs or slug in self.slugs

    def requested_packs(self) -> list[str]:
        """What was asked for, so the planner can report anything that is not installed."""
        if self.slugs:
            return sorted(self.slugs)
        return self.profile.requested_packs() if self.profile else []


@dataclass
class RunningScan:
    """A scan in flight, and everything the progress endpoint needs to describe it."""

    scan_id: str
    target: str
    task: asyncio.Task[None] | None = None
    total: int = 0
    completed: int = 0
    current: str = ""
    state: ScanState = ScanState.QUEUED
    error: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    #: Set when the scan reaches a terminal state, so a streaming client can stop without polling.
    finished: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def percent(self) -> float:
        return round(100.0 * self.completed / self.total, 1) if self.total else 0.0

    def snapshot(self) -> dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "state": self.state.value,
            "completed": self.completed,
            "total": self.total,
            "percent": self.percent,
            "current": self.current,
        }


class ScanService:
    """Owns the database, the plugin registry, and the set of running scans."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.database = Database(settings.storage.database_path)
        self.registry = PluginRegistry(
            settings.plugins,
            api_version=PLUGIN_API_VERSION,
            plugin_config_path=REPO_ROOT / "configs" / "plugins.yaml",
        )
        self.manager = PluginManager(self.registry)
        self.scans = ScanRepository(self.database)
        self.findings = FindingRepository(self.database)
        self.targets = TargetRepository(self.database)
        # Reports were rendered to disk and never recorded, so the Reports page had nothing to list
        # and "generate" appeared to do nothing at all. The repository existed the whole time.
        self.reports = ReportRepository(self.database)
        self._running: dict[str, RunningScan] = {}

    # -- lifecycle --------------------------------------------------------------------------

    async def startup(self) -> None:
        await run_migrations(self.database)
        log.info("api ready", extra={"database": str(self.settings.storage.database_path)})

    async def shutdown(self) -> None:
        """Cancel anything still running, and wait for it.

        A scan holds an open HTTP client against a live target. Letting the process exit without
        cancelling would drop the connection mid-payload and leave the scan row stuck in RUNNING
        forever -- which reads, later, as a scan that is still going.
        """
        for running in list(self._running.values()):
            if running.task and not running.task.done():
                running.task.cancel()
        tasks = [r.task for r in self._running.values() if r.task]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._running.clear()

    # -- reads ------------------------------------------------------------------------------

    def profiles(self) -> list[ScanProfile]:
        return load_all_profiles(root=REPO_ROOT)

    def configured_targets(self) -> list[Any]:
        return load_targets()

    def in_flight(self) -> int:
        """How many scans are executing right now."""
        return sum(1 for r in self._running.values() if r.task and not r.task.done())

    def running(self, scan_id: str) -> RunningScan | None:
        return self._running.get(scan_id)

    async def session(self, scan_id: str) -> ScanSession | None:
        return await self.scans.get(scan_id)

    async def recent(self, limit: int = 20) -> list[ScanSession]:
        return await self.scans.list_recent(limit)

    async def results(self, scan_id: str) -> list[PluginResult]:
        return await self.scans.results_for(scan_id)

    # -- control ----------------------------------------------------------------------------

    def resolve_selection(
        self,
        *,
        profile: ScanProfile | None,
        plugins: list[str],
        categories: list[str],
    ) -> Selection | ScanProfile | None:
        """Turn a request's pack and category choice into something the planner understands.

        Categories are resolved against the registry here, in the application layer, because the
        scheduler is given a predicate rather than metadata -- and resolving them at the boundary
        keeps the scheduler's protocol to the one method it actually needs.
        """
        chosen = set(plugins)
        if categories:
            wanted = {c.strip().lower() for c in categories}
            chosen |= {
                plugin.slug
                for plugin in self.registry.discover().active
                if plugin.metadata().category.strip().lower() in wanted
            }
        if not chosen:
            return profile
        return Selection(slugs=frozenset(chosen), profile=profile)

    async def start(
        self,
        *,
        target_name: str,
        profile_name: str | None,
        plugins: list[str] | None = None,
        categories: list[str] | None = None,
    ) -> RunningScan:
        """Begin a scan and return immediately.

        Everything that can fail synchronously -- unknown target, unknown profile, unauthorized
        target, out-of-scope host -- fails *here*, so the caller gets a 4xx rather than a 202
        followed by a scan that dies a second later.
        """
        target = select_target(load_targets(), target_name)
        profile = load_profile(profile_name, root=REPO_ROOT) if profile_name else None
        settings = load_settings(profile=profile)
        selector = self.resolve_selection(
            profile=profile, plugins=plugins or [], categories=categories or []
        )

        # Constructing the adapter runs the scope check (loopback-only by default). Doing it before
        # the task is spawned is what turns "out of scope" into a 400 instead of a background error.
        adapter = build_adapter(
            target,
            allow_remote=settings.safety.allow_remote_targets,
            allowed_hosts=settings.safety.allowed_hosts,
            retry=settings.engine.retry,
        )

        scan_id = ScanSession.new_id()
        running = RunningScan(scan_id=scan_id, target=target.name)
        self._running[scan_id] = running

        analyzer, _ = build_analyzer(REPO_ROOT / "configs" / "analyzer")
        engine = ScanEngine(
            settings=settings,
            registry=self.registry,
            scheduler=ScanScheduler(max_concurrency=settings.engine.max_concurrency),
            scan_repository=self.scans,
            target_repository=self.targets,
            engine_version=__version__,
            analyzer=analyzer,
            finding_repository=self.findings,
        )

        running.task = asyncio.create_task(
            self._run(engine, running, target=target, adapter=adapter, profile=selector),
            name=f"scan-{scan_id}",
        )
        return running

    async def cancel(self, scan_id: str) -> bool:
        """Cancel a running scan. ``False`` when it was not running."""
        running = self._running.get(scan_id)
        if running is None or running.task is None or running.task.done():
            return False
        running.task.cancel()
        return True

    # -- internals --------------------------------------------------------------------------

    async def _run(
        self,
        engine: ScanEngine,
        running: RunningScan,
        *,
        target: Any,
        adapter: Any,
        profile: ProfileSelector | None,
    ) -> None:
        def on_result(result: PluginResult) -> None:
            # Skipped packs are not progress. The scheduler emits every skip in one block before
            # any real work starts, so counting them made a smoke scan -- 2 packs of 9 -- read
            # "7 / 9 cases" within a second and then sit there for a minute. The bar was measuring
            # the profile's *filter*, not the scan.
            if result.outcome is PluginOutcome.SKIPPED:
                return
            running.completed += 1
            running.current = result.plugin_slug

        def on_plan(runnable: int) -> None:
            # The denominator is what will actually run, not everything installed. Coverage is a
            # separate question with a separate answer -- `session.plugins_total` still counts all
            # nine, so a smoke scan still reports 22% coverage (ADR-020). A progress bar that
            # reads 100% and a coverage figure that reads 22% are both correct: one is asking
            # "is it finished?", the other "how much of the surface did it look at?".
            running.total = runnable

        running.state = ScanState.RUNNING
        try:
            outcome = await engine.run(
                target=target,
                adapter=adapter,
                profile=profile,
                # The client already has this id. The engine must use it rather than mint its own,
                # or `GET /scans/{id}` 404s on the very id `POST /scans` just returned.
                scan_id=running.scan_id,
                on_plan=on_plan,
                on_result=_counting(running, on_result),
            )
            running.state = outcome.session.state
            # Deliberately NOT `plugins_total`: that counts the skipped packs too, so assigning it
            # here would snap a finished 2/2 bar back to 2/9 at the moment it completed.
            running.total = outcome.session.plugins_total - outcome.session.plugins_skipped
        except asyncio.CancelledError:
            running.state = ScanState.CANCELLED
            running.error = "cancelled by request"
            raise
        except RAGStrikeError as exc:
            running.state = ScanState.FAILED
            running.error = f"{exc.code}: {exc.message}"
            log.warning("scan failed", extra={"scan_id": running.scan_id, "error": running.error})
        except Exception as exc:
            running.state = ScanState.FAILED
            running.error = f"{type(exc).__name__}: {exc}"
            log.exception("scan errored", extra={"scan_id": running.scan_id})
        finally:
            running.finished.set()
            await adapter.close()


def _counting(
    running: RunningScan, callback: Callable[[PluginResult], None]
) -> Callable[[PluginResult], None]:
    """Wrap the progress callback so a plugin's own failure cannot stall the counter."""

    def _on(result: PluginResult) -> None:
        try:
            callback(result)
        except Exception:  # pragma: no cover - defensive
            log.exception("progress callback failed", extra={"scan_id": running.scan_id})

    return _on


__all__ = ["RunningScan", "ScanService"]
