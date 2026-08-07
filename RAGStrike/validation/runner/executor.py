"""Benchmark execution: one scan per target, benchmarks read from it.

WHY ONE SCAN PER TARGET AND NOT ONE PER BENCHMARK
    Twenty benchmarks would be twenty scans, each re-running discovery, reconnecting, and re-issuing
    every payload through a local 4-billion-parameter model. That is tens of minutes of identical
    work to produce the same results.

    A scan already executes every installed plugin and returns a result per plugin. Each benchmark
    names the plugins whose behaviour it is a claim about, so it reads its outcome out of that one
    scan. The framework is exercised exactly as an operator would exercise it -- through
    ``ScanEngine`` -- which is also the point: a validation harness that took a shortcut around the
    engine would be validating the shortcut.

WHY OUTCOMES ARE FOLDED, NOT AVERAGED
    A benchmark naming two plugins is one claim, and the fold uses the engine's own precedence
    (FAIL > ERROR > INCONCLUSIVE > PASS > SKIPPED). Anything else would invent an aggregation rule
    the framework does not have, and the validation would then be measuring the harness.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
import time
from typing import Any

from ragstrike import PLUGIN_API_VERSION, __version__
from ragstrike.core.config.loader import REPO_ROOT, load_settings, load_targets, select_target
from ragstrike.core.config.models import Settings
from ragstrike.core.errors import RAGStrikeError
from ragstrike.core.orchestrator.scan_engine import ScanEngine
from ragstrike.database.connection import Database
from ragstrike.database.migrations.runner import run_migrations
from ragstrike.database.repositories.scan_repository import ScanRepository
from ragstrike.database.repositories.target_repository import TargetRepository
from ragstrike.models.entities.scan import PluginResult
from ragstrike.models.values.enums import PluginOutcome
from ragstrike.plugins.registry.plugin_registry import PluginRegistry
from ragstrike.scheduler.scan_scheduler import ScanScheduler
from ragstrike.target_adapters.registry import build_adapter
from validation.benchmarks.models import Benchmark, BenchmarkResult, Outcome, Status

#: The engine's fold precedence, worst first. Mirrored rather than imported so a change to the
#: engine's ordering shows up here as a validation mismatch instead of being silently adopted.
PRECEDENCE: tuple[PluginOutcome, ...] = (
    PluginOutcome.FAIL,
    PluginOutcome.ERROR,
    PluginOutcome.INCONCLUSIVE,
    PluginOutcome.PASS,
    PluginOutcome.SKIPPED,
)


@dataclass(slots=True)
class ScanRecord:
    """One completed scan against one target, indexed for benchmark lookup."""

    target: str
    results: dict[str, PluginResult] = field(default_factory=dict)
    duration_ms: int = 0
    scan_id: str = ""
    error: str = ""
    plugins_discovered: int = 0

    @property
    def ok(self) -> bool:
        return not self.error


def _registry(settings: Settings) -> PluginRegistry:
    return PluginRegistry(
        settings.plugins,
        api_version=PLUGIN_API_VERSION,
        plugin_config_path=REPO_ROOT / "configs" / "plugins.yaml",
    )


async def _scan(settings: Settings, target: Any) -> ScanRecord:
    """Run one real scan through the real engine."""
    record = ScanRecord(target=target.name)
    started = time.perf_counter()

    database = Database(settings.storage.database_path)
    await run_migrations(database)

    registry = _registry(settings)
    engine = ScanEngine(
        settings=settings,
        registry=registry,
        scheduler=ScanScheduler(max_concurrency=settings.engine.max_concurrency),
        scan_repository=ScanRepository(database),
        target_repository=TargetRepository(database),
        engine_version=__version__,
    )

    adapter = build_adapter(
        target,
        allow_remote=settings.safety.allow_remote_targets,
        allowed_hosts=settings.safety.allowed_hosts,
    )

    try:
        outcome = await engine.run(target=target, adapter=adapter)
    except RAGStrikeError as exc:
        # Recorded rather than raised: one unreachable target must not abandon the other half of
        # the comparison, and "could not run" is a distinct validation status from "mismatched".
        record.error = f"{type(exc).__name__}: {exc}"
        return record
    finally:
        await adapter.close()
        record.duration_ms = int((time.perf_counter() - started) * 1000)

    record.results = {result.plugin_slug: result for result in outcome.results}
    record.scan_id = outcome.session.id
    record.plugins_discovered = len(outcome.plan.entries) if hasattr(outcome.plan, "entries") else 0
    return record


def run_scan(target_name: str, *, config: Path | None = None) -> ScanRecord:
    """Scan one target. Synchronous wrapper, because the harness is a script."""
    settings = load_settings(config_file=config)
    targets = load_targets()
    try:
        target = select_target(targets, target_name)
    except RAGStrikeError as exc:
        return ScanRecord(target=target_name, error=f"{type(exc).__name__}: {exc}")
    return asyncio.run(_scan(settings, target))


def fold(outcomes: list[PluginOutcome]) -> PluginOutcome:
    """Combine several plugin outcomes into one, using the engine's precedence."""
    for candidate in PRECEDENCE:
        if candidate in outcomes:
            return candidate
    return PluginOutcome.SKIPPED


def evaluate(benchmark: Benchmark, target: str, record: ScanRecord) -> BenchmarkResult:
    """Judge one benchmark against one scan."""
    expectation = benchmark.expectation_for(target)
    if expectation is None:
        return BenchmarkResult(
            benchmark_id=benchmark.id,
            description=benchmark.description,
            target=target,
            plugins_executed=(),
            expected=Outcome.SKIPPED,
            observed=Outcome.SKIPPED,
            status=Status.NOT_RUN,
            execution_ms=0,
            detail=f"{benchmark.id} declares no expectation for {target}",
        )

    if not record.ok:
        return BenchmarkResult(
            benchmark_id=benchmark.id,
            description=benchmark.description,
            target=target,
            plugins_executed=(),
            expected=expectation.outcome,
            observed=Outcome.ERROR,
            status=Status.NOT_RUN,
            execution_ms=record.duration_ms,
            detail=record.error,
        )

    present = [slug for slug in benchmark.plugins if slug in record.results]
    missing = [slug for slug in benchmark.plugins if slug not in record.results]

    if not present:
        # NOT_RUN rather than MISMATCH: an uninstalled plugin is an environment gap, and counting it
        # as a framework defect would make a partial install look like a broken framework.
        return BenchmarkResult(
            benchmark_id=benchmark.id,
            description=benchmark.description,
            target=target,
            plugins_executed=(),
            expected=expectation.outcome,
            observed=Outcome.SKIPPED,
            status=Status.NOT_RUN,
            execution_ms=0,
            detail=f"plugin(s) not installed or not scheduled: {', '.join(missing)}",
        )

    results = [record.results[slug] for slug in present]
    observed_enum = fold([r.outcome for r in results])
    observed = Outcome(observed_enum.value)
    elapsed = sum(r.elapsed_ms for r in results)

    status = Status.VALIDATED if observed == expectation.outcome else Status.MISMATCH

    # An INCONCLUSIVE that was *expected* is a successful validation of the framework's honesty, not
    # an undetermined result. An INCONCLUSIVE that was not expected is undetermined rather than a
    # mismatch: the framework declined to claim, which is weaker evidence than a wrong claim.
    if observed is Outcome.INCONCLUSIVE and expectation.outcome is not Outcome.INCONCLUSIVE:
        status = Status.UNDETERMINED

    detail = "; ".join(f"{r.plugin_slug}={r.outcome.value}" for r in results)
    if missing:
        detail += f" (not scheduled: {', '.join(missing)})"

    return BenchmarkResult(
        benchmark_id=benchmark.id,
        description=benchmark.description,
        target=target,
        plugins_executed=tuple(present),
        expected=expectation.outcome,
        observed=observed,
        status=status,
        execution_ms=elapsed,
        detail=detail,
        findings=sum(1 for r in results if r.outcome is PluginOutcome.FAIL),
        severity=_severity_of(results),
    )


def _severity_of(results: list[PluginResult]) -> str:
    """Highest severity reported by any failing plugin in the set.

    Read from the plugin's evidence rather than recomputed. The analyzer owns severity, and a second
    derivation here could disagree with the report an operator is reading.
    """
    order = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
    seen = {
        str(r.evidence.get("severity", "")).upper()
        for r in results
        if r.outcome is PluginOutcome.FAIL
    }
    return next((level for level in order if level in seen), "")
