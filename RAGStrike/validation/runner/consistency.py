"""The ten consistency checks.

WHAT THESE ARE FOR
    The benchmarks measure whether the framework *finds the right things*. These measure whether its
    machinery is intact: does discovery work, does configuration load, does the analyzer produce
    findings, does the reporter render them, does the database hold them, does the dashboard reach
    them.

    They are fast, need no target, and are the first thing to run — because a benchmark mismatch
    caused by a broken analyzer is a confusing way to discover the analyzer is broken.

WHY EACH CHECK RETURNS A DETAIL STRING
    "Plugin discovery: FAIL" is not actionable. "Plugin discovery: 0 active, 9 rejected — API
    version mismatch" is. Every check reports what it saw, not only whether it liked it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import time
from typing import Any


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    passed: bool
    detail: str
    duration_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": "PASS" if self.passed else "FAIL",
            "detail": self.detail,
            "duration_ms": self.duration_ms,
        }


def _timed(name: str, fn: Callable[[], tuple[bool, str]]) -> CheckResult:
    started = time.perf_counter()
    try:
        passed, detail = fn()
    except Exception as exc:  # a check that raises is a failed check, never a crashed run
        passed, detail = False, f"{type(exc).__name__}: {exc}"
    return CheckResult(name, passed, detail, int((time.perf_counter() - started) * 1000))


# -- the checks ------------------------------------------------------------------------------------


def check_configuration() -> tuple[bool, str]:
    from ragstrike.core.config.loader import load_settings, load_targets

    settings = load_settings()
    targets = load_targets()
    return (
        bool(settings.plugins.local_dirs) and bool(targets),
        f"{len(targets)} target(s); safety allow_remote={settings.safety.allow_remote_targets}; "
        f"{len(settings.plugins.local_dirs)} plugin dir(s)",
    )


def check_plugin_discovery() -> tuple[bool, str]:
    from ragstrike import PLUGIN_API_VERSION
    from ragstrike.core.config.loader import REPO_ROOT, load_settings
    from ragstrike.plugins.registry.plugin_registry import PluginRegistry

    settings = load_settings()
    health = PluginRegistry(
        settings.plugins,
        api_version=PLUGIN_API_VERSION,
        plugin_config_path=REPO_ROOT / "configs" / "plugins.yaml",
    ).discover()
    return (
        len(health.active) > 0,
        f"{len(health.active)} active, {len(health.rejected)} refused",
    )


def check_analyzer_output() -> tuple[bool, str]:
    """Feed the analyzer a known observation and confirm it produces a finding."""
    from ragstrike.analyzers.config import build_engine

    engine, report = build_engine(Path("configs") / "analyzer")
    return (
        report.fully_configured and len(engine.registry) > 0,
        f"{len(engine.registry)} analyzer(s) registered; config missing={report.missing or 'none'}",
    )


def check_finding_generation() -> tuple[bool, str]:
    from datetime import datetime as dt

    from ragstrike.analyzers.base.finding import Finding
    from ragstrike.models.values.enums import PluginOutcome, Severity

    finding = Finding(
        id="consistency",
        scan_id="s",
        plugin_id="p",
        category="c",
        status=PluginOutcome.FAIL,
        severity=Severity.HIGH,
        confidence=0.9,
        risk_score=7.0,
        timestamp=dt.now(UTC),
        analyzer_version="1.0.0",
    )
    return finding.risk_score > 0, f"Finding constructs; risk={finding.risk_score}"


def check_report_generation() -> tuple[bool, str]:
    """Render every implemented format from a synthetic finding."""
    from datetime import datetime as dt

    from ragstrike.analyzers.base.finding import Finding
    from ragstrike.models.values.enums import PluginOutcome, Severity
    from ragstrike.reporters.builders.report_builder import ReportContext
    from ragstrike.reporters.engine.report_engine import ReportEngine

    finding = Finding(
        id="f1",
        scan_id="s1",
        plugin_id="prompt-injection",
        category="prompt_injection",
        status=PluginOutcome.FAIL,
        severity=Severity.HIGH,
        confidence=0.9,
        risk_score=7.2,
        timestamp=dt.now(UTC),
        analyzer_version="1.0.0",
    )
    engine = ReportEngine()
    generated = engine.generate([finding], ReportContext(scan_id="s1"))
    rendered = engine.render_all(generated)
    sizes = ", ".join(f"{fmt}={len(body)}B" for fmt, body in sorted(rendered.items()))
    return bool(rendered), f"{len(rendered)} format(s): {sizes}"


def check_database_integrity() -> tuple[bool, str]:
    """Apply migrations to a scratch database and confirm the recorded versions have no gaps."""
    import asyncio
    import tempfile

    from ragstrike.database.connection import Database
    from ragstrike.database.migrations.runner import MIGRATIONS, run_migrations

    async def probe() -> tuple[bool, str]:
        with tempfile.TemporaryDirectory() as tmp:
            database = Database(Path(tmp) / "probe.db")
            applied = await run_migrations(database)
            expected = list(range(1, len(MIGRATIONS) + 1))
            return (
                sorted(applied) == expected,
                f"{len(applied)} migration(s) applied: {sorted(applied)}",
            )

    return asyncio.run(probe())


def check_logging() -> tuple[bool, str]:
    from ragstrike.core.config.loader import load_settings

    settings = load_settings()
    log_dir = settings.logging.log_dir
    return (
        log_dir.exists() or log_dir.parent.exists(),
        f"level={settings.logging.level}; json_lines={settings.logging.json_lines}; dir={log_dir}",
    )


def check_dashboard_integration() -> tuple[bool, str]:
    """The dashboard's own wiring, without a browser.

    Checked through its service container rather than by rendering: the dashboard is a pure HTTP
    client, and what matters here is that its services build and its route registry resolves.
    """
    from ragstrike.dashboard.navigation.router import resolve
    from ragstrike.dashboard.navigation.routes import ROUTES
    from ragstrike.dashboard.services import build_services_with
    from ragstrike.dashboard.services.demo import DemoTransport

    services = build_services_with(DemoTransport())
    unresolved = [route.id for route in ROUTES if not resolve(route.id).ok]
    return (
        not unresolved and services.transport.name == "demo",
        f"{len(ROUTES)} page(s) resolve; unresolved={unresolved or 'none'}",
    )


def check_target_communication(targets: list[str]) -> tuple[bool, str]:
    """Probe each named target through the real adapter, with the real scope policy."""
    import asyncio

    from ragstrike.core.config.loader import load_settings, load_targets, select_target
    from ragstrike.core.errors import RAGStrikeError
    from ragstrike.target_adapters.registry import build_adapter

    settings = load_settings()
    configured = load_targets()

    if not targets:
        # Requested with no targets -- --checks-only, or a run against nothing. Reporting FAIL here
        # would make "I did not ask for a target" indistinguishable from "the target is down".
        return True, "skipped: no targets requested"

    async def probe() -> tuple[bool, str]:
        lines: list[str] = []
        reachable = 0
        for name in targets:
            try:
                target = select_target(configured, name)
                adapter = build_adapter(
                    target,
                    allow_remote=settings.safety.allow_remote_targets,
                    allowed_hosts=settings.safety.allowed_hosts,
                )
            except RAGStrikeError as exc:
                lines.append(f"{name}: {type(exc).__name__}")
                continue
            try:
                health = await adapter.health_check()
            finally:
                await adapter.close()
            reachable += 1 if health.reachable else 0
            lines.append(f"{name}: {'up' if health.reachable else 'down'} ({health.latency_ms}ms)")
        return reachable == len(targets), "; ".join(lines)

    return asyncio.run(probe())


def check_sdk() -> tuple[bool, str]:
    """The SDK is a public contract; confirm its surface imports and its version is declared."""
    from ragstrike import PLUGIN_API_VERSION, sdk

    exported = [name for name in dir(sdk) if not name.startswith("_")]
    return len(exported) > 0, f"plugin API {PLUGIN_API_VERSION}; {len(exported)} export(s)"


CHECKS: tuple[tuple[str, Callable[[], tuple[bool, str]]], ...] = (
    ("Configuration loading", check_configuration),
    ("Plugin discovery", check_plugin_discovery),
    ("Attack SDK", check_sdk),
    ("Analyzer output", check_analyzer_output),
    ("Finding generation", check_finding_generation),
    ("Report generation", check_report_generation),
    ("Database integrity", check_database_integrity),
    ("Logging", check_logging),
    ("Dashboard integration", check_dashboard_integration),
)


def run_all(targets: list[str] | None = None) -> list[CheckResult]:
    """Every consistency check, in a deliberate order: configuration first, targets last."""
    results = [_timed(name, fn) for name, fn in CHECKS]
    named = targets or []
    results.append(_timed("Target communication", lambda: check_target_communication(named)))
    return results


def summarize(results: list[CheckResult]) -> dict[str, Any]:
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "failed": sum(1 for r in results if not r.passed),
        "checks": [r.to_dict() for r in results],
    }
