"""Extended lifecycle tests.

Phase 3 tested plan/execute/analyze/result. Phase 4 added healthcheck/setup/cleanup around them
and events at the boundaries. These tests cover the two invariants that matter operationally:

* **Cleanup always runs**, even when execute() raises or healthcheck fails.
* **Events fire in a fixed order**, so a subscriber can rely on STARTED then FINISHED (or FAILED).
"""

from __future__ import annotations

import pytest
from tests.conftest import FakeTarget

from ragstrike import PLUGIN_API_VERSION
from ragstrike.core.config.models import PluginSettings
from ragstrike.models.values.enums import Capability, PluginOutcome
from ragstrike.plugins.base.reports import Check, HealthReport
from ragstrike.plugins.events import InMemoryBus, PluginEventType
from ragstrike.plugins.registry.plugin_registry import PluginRegistry
from ragstrike.scheduler.scan_scheduler import ScanScheduler


def load(directory, **overrides) -> list:
    settings = PluginSettings(local_dirs=[directory], **overrides)
    return PluginRegistry(settings, api_version=PLUGIN_API_VERSION).discover().active


# ------------------------------------------------------------------------------------------------
# Cleanup always runs
# ------------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_runs_on_success(make_plugin) -> None:
    plugins = load(make_plugin("fixture-attack"))
    plugin = plugins[0]
    seen = {"cleanup": False}

    original = plugin.attack.cleanup

    def spy() -> None:
        seen["cleanup"] = True
        original()

    plugin.attack.cleanup = spy  # type: ignore[method-assign]
    scheduler = ScanScheduler()
    plan = scheduler.plan(plugins, (Capability.CHAT,))

    await scheduler.run(scan_id="s1", plan=plan, target=FakeTarget())

    assert seen["cleanup"] is True


@pytest.mark.asyncio
async def test_cleanup_runs_even_when_execute_raises(make_plugin) -> None:
    """The finally block is the isolation boundary. A plugin that leaks state on error is a
    plugin that corrupts the next scan; running cleanup guarantees it does not."""
    plugins = load(make_plugin("angry-attack"))
    plugin = plugins[0]
    seen = {"cleanup": False}

    async def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    plugin.attack.execute = boom  # type: ignore[method-assign]
    plugin.attack.cleanup = lambda: seen.__setitem__("cleanup", True)  # type: ignore[method-assign]

    scheduler = ScanScheduler()
    plan = scheduler.plan(plugins, (Capability.CHAT,))
    results = await scheduler.run(scan_id="s1", plan=plan, target=FakeTarget())

    assert results[0].outcome is PluginOutcome.ERROR
    assert seen["cleanup"] is True


@pytest.mark.asyncio
async def test_cleanup_error_does_not_change_the_outcome(make_plugin) -> None:
    """A cleanup that throws must not turn a passing scan into an errored one -- it is a plugin
    bug the log reports, not a downgrade of the actual result."""
    plugins = load(make_plugin("fixture-attack"))
    plugins[0].attack.cleanup = lambda: (_ for _ in ()).throw(RuntimeError("leak"))  # type: ignore[method-assign]

    scheduler = ScanScheduler()
    plan = scheduler.plan(plugins, (Capability.CHAT,))
    results = await scheduler.run(scan_id="s1", plan=plan, target=FakeTarget())

    assert results[0].outcome is PluginOutcome.PASS


# ------------------------------------------------------------------------------------------------
# Healthcheck
# ------------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unhealthy_plugin_is_skipped_with_the_failing_rule(make_plugin) -> None:
    plugins = load(make_plugin("fussy-attack"))
    plugins[0].attack.healthcheck = lambda: HealthReport(  # type: ignore[method-assign]
        checks=[Check(rule="needs-canary", passed=False, detail="target does not support ingest")]
    )

    scheduler = ScanScheduler()
    plan = scheduler.plan(plugins, (Capability.CHAT,))
    results = await scheduler.run(scan_id="s1", plan=plan, target=FakeTarget())

    assert results[0].outcome is PluginOutcome.SKIPPED
    assert "target does not support ingest" in results[0].summary


@pytest.mark.asyncio
async def test_healthcheck_exception_is_an_error_not_a_skip(make_plugin) -> None:
    """A crashing healthcheck is a plugin bug. Reporting it as SKIPPED would hide it."""
    plugins = load(make_plugin("crashy-attack"))
    plugins[0].attack.healthcheck = lambda: (_ for _ in ()).throw(RuntimeError("broken"))  # type: ignore[method-assign]

    scheduler = ScanScheduler()
    plan = scheduler.plan(plugins, (Capability.CHAT,))
    results = await scheduler.run(scan_id="s1", plan=plan, target=FakeTarget())

    assert results[0].outcome is PluginOutcome.ERROR


# ------------------------------------------------------------------------------------------------
# Events
# ------------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_events_fire_in_order_for_a_passing_plugin(make_plugin) -> None:
    plugins = load(make_plugin("fixture-attack"))
    bus = InMemoryBus()
    scheduler = ScanScheduler(event_bus=bus)
    plan = scheduler.plan(plugins, (Capability.CHAT,))

    await scheduler.run(scan_id="s1", plan=plan, target=FakeTarget())

    types = [e.type for e in bus.events]
    assert types == [PluginEventType.STARTED, PluginEventType.FINISHED]


@pytest.mark.asyncio
async def test_failed_event_fires_when_execute_raises(make_plugin) -> None:
    plugins = load(make_plugin("angry-attack"))

    async def boom(*_a, **_kw):
        raise RuntimeError("boom")

    plugins[0].attack.execute = boom  # type: ignore[method-assign]

    bus = InMemoryBus()
    scheduler = ScanScheduler(event_bus=bus)
    plan = scheduler.plan(plugins, (Capability.CHAT,))
    await scheduler.run(scan_id="s1", plan=plan, target=FakeTarget())

    assert any(e.type is PluginEventType.FAILED for e in bus.events)
