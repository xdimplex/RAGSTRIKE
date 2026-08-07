"""Scheduler tests.

Planning is pure, so it is tested exhaustively without a target. That matters more than it sounds:
scheduling bugs are invisible in the output. A plugin that was silently never scheduled looks
exactly like a plugin that ran and found nothing.
"""

from __future__ import annotations

import asyncio

import pytest
from tests.conftest import FakeTarget

from ragstrike import PLUGIN_API_VERSION
from ragstrike.core.config.models import PluginSettings
from ragstrike.core.config.profiles import ScanProfile
from ragstrike.models.values.enums import Capability, PluginOutcome
from ragstrike.plugins.registry.plugin_registry import PluginRegistry
from ragstrike.scheduler.scan_scheduler import ScanScheduler


def load(directory, **overrides) -> list:
    settings = PluginSettings(local_dirs=[directory], **overrides)
    return PluginRegistry(settings, api_version=PLUGIN_API_VERSION).discover().active


# ------------------------------------------------------------------------------------------------
# Planning
# ------------------------------------------------------------------------------------------------


def test_plans_every_applicable_plugin(make_plugin) -> None:
    plugins = load(make_plugin("fixture-attack"))

    plan = ScanScheduler().plan(plugins, (Capability.CHAT,))

    assert len(plan.runnable) == 1
    assert plan.skipped == []
    assert plan.total == 1


def test_skips_plugins_whose_capability_is_missing(make_plugin) -> None:
    plugins = load(make_plugin("ingest-attack", capability="Capability.INGEST_DOCUMENT"))

    plan = ScanScheduler().plan(plugins, (Capability.CHAT,))

    assert plan.runnable == []
    assert len(plan.skipped) == 1
    assert "INGEST_DOCUMENT" in plan.skipped[0][1]


def test_skipped_plugins_still_count_toward_the_total(make_plugin) -> None:
    """Coverage is executed/applicable. A skipped plugin is a gap, and gaps must be countable."""
    plugins_dir = make_plugin("chat-attack")
    make_plugin("ingest-attack", directory=plugins_dir, capability="Capability.INGEST_DOCUMENT")

    plan = ScanScheduler().plan(load(plugins_dir), (Capability.CHAT,))

    assert plan.total == 2
    assert len(plan.runnable) == 1


def test_unverified_target_attempts_everything(make_plugin) -> None:
    """An empty capability set means "unknown", not "supports nothing".

    Treating it as the latter would make the first scan against a fresh target skip every plugin
    and then report full coverage of nothing.
    """
    plugins = load(make_plugin("ingest-attack", capability="Capability.INGEST_DOCUMENT"))

    plan = ScanScheduler().plan(plugins, ())

    assert len(plan.runnable) == 1


def test_planning_performs_no_io(make_plugin) -> None:
    """No target is involved, which is what makes the plan exhaustively testable."""
    plan = ScanScheduler().plan(load(make_plugin("fixture-attack")), (Capability.CHAT,))

    assert plan.total == 1


# ------------------------------------------------------------------------------------------------
# Execution
# ------------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runs_a_plugin_and_returns_its_result(make_plugin) -> None:
    plugins = load(make_plugin("fixture-attack"))
    scheduler = ScanScheduler()
    plan = scheduler.plan(plugins, (Capability.CHAT,))
    target = FakeTarget()

    results = await scheduler.run(scan_id="s1", plan=plan, target=target)

    assert len(results) == 1
    assert results[0].outcome is PluginOutcome.PASS
    assert results[0].plugin_slug == "fixture-attack"
    assert target.prompts == ["ping"]


@pytest.mark.asyncio
async def test_a_failing_plugin_is_reported_as_fail(make_plugin) -> None:
    plugins = load(make_plugin("vuln-attack", outcome="FAIL"))
    scheduler = ScanScheduler()
    plan = scheduler.plan(plugins, (Capability.CHAT,))

    results = await scheduler.run(scan_id="s1", plan=plan, target=FakeTarget())

    assert results[0].outcome is PluginOutcome.FAIL


@pytest.mark.asyncio
async def test_skipped_plugins_appear_in_the_results(make_plugin) -> None:
    plugins = load(make_plugin("ingest-attack", capability="Capability.INGEST_DOCUMENT"))
    scheduler = ScanScheduler()
    plan = scheduler.plan(plugins, (Capability.CHAT,))

    results = await scheduler.run(scan_id="s1", plan=plan, target=FakeTarget())

    assert results[0].outcome is PluginOutcome.SKIPPED
    assert "INGEST_DOCUMENT" in results[0].summary


@pytest.mark.asyncio
async def test_one_exploding_plugin_does_not_lose_the_others(make_plugin) -> None:
    """The isolation boundary. One broken plugin must never end a scan."""
    plugins_dir = make_plugin("good-attack")
    make_plugin("angry-attack", directory=plugins_dir)

    plugins = load(plugins_dir)
    angry = next(p for p in plugins if p.slug == "angry-attack")
    angry.attack.payloads = lambda: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore[method-assign]

    scheduler = ScanScheduler()
    plan = scheduler.plan(plugins, (Capability.CHAT,))
    results = await scheduler.run(scan_id="s1", plan=plan, target=FakeTarget())

    by_slug = {r.plugin_slug: r for r in results}
    assert by_slug["good-attack"].outcome is PluginOutcome.PASS
    assert by_slug["angry-attack"].outcome is PluginOutcome.ERROR
    assert "boom" in by_slug["angry-attack"].error


@pytest.mark.asyncio
async def test_target_errors_become_error_results_not_exceptions(make_plugin) -> None:
    plugins = load(make_plugin("fixture-attack"))
    scheduler = ScanScheduler()
    plan = scheduler.plan(plugins, (Capability.CHAT,))

    results = await scheduler.run(
        scan_id="s1", plan=plan, target=FakeTarget(raises=ConnectionError("refused"))
    )

    assert results[0].outcome is PluginOutcome.ERROR


@pytest.mark.asyncio
async def test_cancellation_propagates(make_plugin) -> None:
    """Cancellation is control flow, not a plugin failure. Swallowing it would hang a scan."""
    plugins = load(make_plugin("fixture-attack"))
    plugin = plugins[0]

    async def cancel(*_args, **_kwargs):
        raise asyncio.CancelledError

    plugin.attack.execute = cancel  # type: ignore[method-assign]
    scheduler = ScanScheduler()
    plan = scheduler.plan(plugins, (Capability.CHAT,))

    with pytest.raises(asyncio.CancelledError):
        await scheduler.run(scan_id="s1", plan=plan, target=FakeTarget())


@pytest.mark.asyncio
async def test_progress_callback_fires_per_result(make_plugin) -> None:
    plugins_dir = make_plugin("one-attack")
    make_plugin("two-attack", directory=plugins_dir)
    scheduler = ScanScheduler()
    plan = scheduler.plan(load(plugins_dir), (Capability.CHAT,))

    seen: list[str] = []
    await scheduler.run(
        scan_id="s1", plan=plan, target=FakeTarget(), on_result=lambda r: seen.append(r.plugin_slug)
    )

    assert sorted(seen) == ["one-attack", "two-attack"]


@pytest.mark.asyncio
async def test_plugins_run_sequentially(make_plugin) -> None:
    """Phase 3 is sequential by design; concurrency is planned, not implemented."""
    plugins_dir = make_plugin("one-attack")
    make_plugin("two-attack", directory=plugins_dir)
    scheduler = ScanScheduler(max_concurrency=8)
    plan = scheduler.plan(load(plugins_dir), (Capability.CHAT,))
    target = FakeTarget()

    await scheduler.run(scan_id="s1", plan=plan, target=target)

    assert len(target.prompts) == 2


def test_a_profile_narrows_the_plan_and_records_the_exclusion(make_plugin) -> None:
    """Out of profile is a recorded skip, never a silent omission.

    A quick scan and a full scan must not produce the same-looking report. Anything the profile
    excludes lands in ``plan.skipped`` with a reason, and therefore in the coverage section
    (ADR-020).

    This test is the wire between profile loading and planning. If that wire is ever cut -- which is
    exactly what happened between Phase 1 and Phase 16, when the profile files existed and nothing
    read them -- this fails.
    """
    plugins_dir = make_plugin("wanted")
    make_plugin("unwanted", directory=plugins_dir)
    plugins = load(plugins_dir)
    profile = ScanProfile(id="narrow", packs=["wanted"])

    plan = ScanScheduler().plan(plugins, (Capability.CHAT,), profile=profile)

    assert [p.slug for p in plan.runnable] == ["wanted"]
    assert [(p.slug, reason) for p, reason in plan.skipped] == [
        ("unwanted", "not selected by the active scan profile")
    ]
    assert plan.total == 2


def test_no_profile_runs_everything(make_plugin) -> None:
    plugins_dir = make_plugin("one")
    make_plugin("two", directory=plugins_dir)

    plan = ScanScheduler().plan(load(plugins_dir), (Capability.CHAT,))

    assert len(plan.runnable) == 2
    assert plan.skipped == []


def test_a_cancelled_scan_reaches_a_terminal_state(make_plugin, tmp_path) -> None:
    """``asyncio.CancelledError`` derives from ``BaseException``, not ``Exception``.

    Neither of the engine's handlers caught it, so a cancelled scan left its database row in
    PREPARING or RUNNING permanently. Two such rows were found in the development database, and a
    scan stuck in RUNNING reads -- months later -- as one that is still going.
    """
    import asyncio

    from ragstrike.core.config.models import Settings, StorageSettings
    from ragstrike.core.orchestrator.scan_engine import ScanEngine
    from ragstrike.database.connection import Database
    from ragstrike.database.migrations.runner import run_migrations
    from ragstrike.database.repositories.scan_repository import ScanRepository
    from ragstrike.database.repositories.target_repository import TargetRepository
    from ragstrike.models.entities.target import Authorization, Target
    from ragstrike.models.values.enums import ScanState

    class SlowTarget(FakeTarget):
        async def health_check(self):  # type: ignore[no-untyped-def]
            await asyncio.sleep(30)  # long enough to be cancelled mid-prepare
            return await super().health_check()

    async def run() -> ScanState:
        database = Database(tmp_path / "scans.db")
        await run_migrations(database)
        settings = Settings(
            storage=StorageSettings(
                database_path=tmp_path / "scans.db", reports_dir=tmp_path / "reports"
            )
        )
        scans = ScanRepository(database)
        engine = ScanEngine(
            settings=settings,
            registry=PluginRegistry(
                PluginSettings(local_dirs=[make_plugin("cancel-me")]),
                api_version=PLUGIN_API_VERSION,
            ),
            scheduler=ScanScheduler(),
            scan_repository=scans,
            target_repository=TargetRepository(database),
            engine_version="test",
        )
        target = Target(
            id="t1",
            name="lab",
            adapter="fake",
            url="http://127.0.0.1:9000",
            authorization=Authorization(authorized_by="tester", authorization_ref="LOCAL"),
        )
        scan_id = "cancel-test-scan"
        task = asyncio.create_task(engine.run(target=target, adapter=SlowTarget(), scan_id=scan_id))
        await asyncio.sleep(0.2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        session = await scans.get(scan_id)
        assert session is not None
        return session.state

    state = asyncio.run(run())

    assert state is ScanState.CANCELLED
    assert state not in {ScanState.QUEUED, ScanState.PREPARING, ScanState.RUNNING}


def test_a_profile_naming_an_uninstalled_pack_records_it(make_plugin) -> None:
    """The defect that made ``--profile quick`` run two packs while its file said four.

    An uninstalled pack is absent from the plugin list, so nothing iterated over it, nothing skipped
    it, and nothing reported it. The scan was narrower than the configuration implied and no line
    anywhere said so.
    """
    plugins = load(make_plugin("real-pack"))
    profile = ScanProfile(id="aspirational", packs=["real-pack", "never-built", "also-missing"])

    plan = ScanScheduler().plan(plugins, (Capability.CHAT,), profile=profile)

    assert [p.slug for p in plan.runnable] == ["real-pack"]
    assert plan.missing == ["also-missing", "never-built"]


def test_missing_packs_do_not_inflate_the_plan_total() -> None:
    """A pack nobody built is a coverage gap, not a plan item.

    Counting it toward ``total`` would make coverage look worse than the installed set warrants;
    counting it toward ``runnable`` would be a lie. It is reported separately.
    """
    profile = ScanProfile(id="ghosts", packs=["never-built"])

    plan = ScanScheduler().plan([], (Capability.CHAT,), profile=profile)

    assert plan.total == 0
    assert plan.missing == ["never-built"]


def test_no_profile_means_nothing_is_missing(make_plugin) -> None:
    """Without a profile there is no requested list, so nothing can be absent from it."""
    plan = ScanScheduler().plan(load(make_plugin("solo")), (Capability.CHAT,))

    assert plan.missing == []


def test_a_wildcard_profile_never_reports_missing_packs(make_plugin) -> None:
    """``packs: ["*"]`` expands to the empty list, which means "everything installed"."""
    profile = ScanProfile(id="everything", packs=["*"])

    plan = ScanScheduler().plan(load(make_plugin("anything")), (Capability.CHAT,), profile=profile)

    assert plan.missing == []
    assert len(plan.runnable) == 1
