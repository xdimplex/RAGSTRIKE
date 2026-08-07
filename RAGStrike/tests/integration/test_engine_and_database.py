"""Engine and database integration tests.

Real SQLite, real migrations, real plugin loading from a real directory. Everything is genuine
except the target, which is the boundary that keeps these deterministic and offline.
"""

from __future__ import annotations

import pytest
from tests.conftest import FakeTarget, make_database

from ragstrike import PLUGIN_API_VERSION, __version__
from ragstrike.core.config.models import PluginSettings
from ragstrike.core.errors import AuthorizationError, TargetUnreachableError
from ragstrike.core.orchestrator.scan_engine import ScanEngine
from ragstrike.database.connection import Database
from ragstrike.database.migrations.runner import run_migrations
from ragstrike.database.repositories.scan_repository import ScanRepository
from ragstrike.database.repositories.target_repository import TargetRepository
from ragstrike.models.values.enums import Capability, PluginOutcome, ScanState
from ragstrike.plugins.registry.plugin_registry import PluginRegistry
from ragstrike.scheduler.scan_scheduler import ScanScheduler


async def build_engine(settings, plugins_dir, database=None) -> tuple[ScanEngine, Database]:
    database = database or await make_database(settings)
    registry = PluginRegistry(
        PluginSettings(local_dirs=[plugins_dir]), api_version=PLUGIN_API_VERSION
    )
    engine = ScanEngine(
        settings=settings,
        registry=registry,
        scheduler=ScanScheduler(),
        scan_repository=ScanRepository(database),
        target_repository=TargetRepository(database),
        engine_version=__version__,
    )
    return engine, database


# ------------------------------------------------------------------------------------------------
# Database initialization
# ------------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_migrations_create_the_three_tables(settings) -> None:
    database = await make_database(settings)

    async with database.connect() as conn:
        cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row["name"] for row in await cursor.fetchall()}

    assert {"targets", "scan_sessions", "plugin_results"} <= tables


@pytest.mark.asyncio
async def test_migrations_are_idempotent(settings) -> None:
    database = Database(settings.storage.database_path)

    first = await run_migrations(database)
    second = await run_migrations(database)

    # Every released migration applies on the first run; none reapply on the second.
    assert first  # non-empty
    assert 1 in first
    assert second == []


@pytest.mark.asyncio
async def test_database_reports_health(settings) -> None:
    database = await make_database(settings)

    healthy, detail = await database.healthy()

    assert healthy and detail == ""


# ------------------------------------------------------------------------------------------------
# The scan lifecycle
# ------------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_lifecycle_completes_and_stores_everything(
    settings, make_plugin, authorized_target
) -> None:
    """The Phase 3 acceptance path: load, discover, connect, execute, store, finish."""
    engine, database = await build_engine(settings, make_plugin("fixture-attack"))

    outcome = await engine.run(target=authorized_target, adapter=FakeTarget())

    assert outcome.session.state is ScanState.COMPLETED
    assert outcome.session.plugins_executed == 1
    assert outcome.session.plugins_passed == 1
    assert outcome.session.coverage == 1.0
    assert outcome.session.finished_at is not None

    stored = await ScanRepository(database).get(outcome.session.id)
    assert stored is not None
    assert stored.state is ScanState.COMPLETED
    assert stored.plugin_inventory == {"fixture-attack": "1.0.0"}

    results = await ScanRepository(database).results_for(outcome.session.id)
    assert len(results) == 1
    assert results[0].outcome is PluginOutcome.PASS


@pytest.mark.asyncio
async def test_the_target_is_recorded(settings, make_plugin, authorized_target) -> None:
    engine, database = await build_engine(settings, make_plugin("fixture-attack"))

    await engine.run(target=authorized_target, adapter=FakeTarget())

    stored = await TargetRepository(database).get_by_name(authorized_target.name)
    assert stored is not None
    assert stored.authorization is not None
    assert stored.authorization.authorized_by == "tester"


@pytest.mark.asyncio
async def test_rescanning_reuses_the_target_row(settings, make_plugin, authorized_target) -> None:
    """Keyed on name, not id: targets.yaml mints a fresh id per load, and keying on it would
    orphan the scan history from every previous run."""
    engine, database = await build_engine(settings, make_plugin("fixture-attack"))

    first = await engine.run(target=authorized_target, adapter=FakeTarget())
    second = await engine.run(target=authorized_target, adapter=FakeTarget())

    assert first.session.target_id == second.session.target_id
    assert len(await TargetRepository(database).list_all()) == 1


@pytest.mark.asyncio
async def test_config_snapshot_is_stored_on_the_scan(
    settings, make_plugin, authorized_target
) -> None:
    """So a result from six months ago can still be explained."""
    engine, database = await build_engine(settings, make_plugin("fixture-attack"))

    outcome = await engine.run(target=authorized_target, adapter=FakeTarget())

    async with database.connect() as conn:
        cursor = await conn.execute(
            "SELECT config_snapshot FROM scan_sessions WHERE id = ?", (outcome.session.id,)
        )
        row = await cursor.fetchone()

    assert row is not None and "max_concurrency" in row["config_snapshot"]


@pytest.mark.asyncio
async def test_scan_runs_with_no_plugins_installed(settings, tmp_path, authorized_target) -> None:
    """The engine must be correct before any scanner exists -- that is the whole phase."""
    empty = tmp_path / "no_plugins"
    empty.mkdir()
    engine, _ = await build_engine(settings, empty)

    outcome = await engine.run(target=authorized_target, adapter=FakeTarget())

    assert outcome.session.state is ScanState.COMPLETED
    assert outcome.session.plugins_total == 0
    assert outcome.results == []


# ------------------------------------------------------------------------------------------------
# Refusals and failures
# ------------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unauthorized_target_is_refused(settings, make_plugin, unauthorized_target) -> None:
    """No scan starts without an authorization record (ADR-017)."""
    engine, _ = await build_engine(settings, make_plugin("fixture-attack"))

    with pytest.raises(AuthorizationError) as caught:
        await engine.run(target=unauthorized_target, adapter=FakeTarget())

    assert "authorization" in caught.value.hint.lower()


@pytest.mark.asyncio
async def test_authorization_can_be_waived_by_configuration(
    lab_root, make_plugin, unauthorized_target
) -> None:
    (lab_root / "configs" / "ragstrike.yaml").write_text(
        "version: 1\nlogging:\n  console: false\nsafety:\n  require_authorization: false\n",
        encoding="utf-8",
    )
    from ragstrike.core.config.loader import load_settings

    settings = load_settings(root=lab_root)
    engine, _ = await build_engine(settings, make_plugin("fixture-attack"))

    outcome = await engine.run(target=unauthorized_target, adapter=FakeTarget())

    assert outcome.session.state is ScanState.COMPLETED


@pytest.mark.asyncio
async def test_unreachable_target_fails_the_scan_and_records_it(
    settings, make_plugin, authorized_target
) -> None:
    """A crashed scan must leave a record. Silence is indistinguishable from never having run."""
    engine, database = await build_engine(settings, make_plugin("fixture-attack"))

    with pytest.raises(TargetUnreachableError):
        await engine.run(target=authorized_target, adapter=FakeTarget(reachable=False))

    scans = await ScanRepository(database).list_recent()
    assert len(scans) == 1
    assert scans[0].state is ScanState.FAILED
    assert "target_unreachable" in scans[0].error


@pytest.mark.asyncio
async def test_a_failing_plugin_marks_the_outcome(settings, make_plugin, authorized_target) -> None:
    engine, _ = await build_engine(settings, make_plugin("vuln-attack", outcome="FAIL"))

    outcome = await engine.run(target=authorized_target, adapter=FakeTarget())

    assert outcome.has_failures
    assert outcome.session.plugins_failed == 1


@pytest.mark.asyncio
async def test_capability_mismatch_lowers_coverage(
    settings, make_plugin, authorized_target
) -> None:
    """A scan that skipped half its plugins must not read the same as one that ran them all."""
    plugins_dir = make_plugin("chat-attack")
    make_plugin("ingest-attack", directory=plugins_dir, capability="Capability.INGEST_DOCUMENT")
    engine, _ = await build_engine(settings, plugins_dir)

    outcome = await engine.run(
        target=authorized_target, adapter=FakeTarget(capabilities=(Capability.CHAT,))
    )

    assert outcome.session.plugins_total == 2
    assert outcome.session.plugins_skipped == 1
    assert outcome.session.coverage == 0.5


async def _analysing_engine(lab_root, make_plugin, slug: str = "analysed-attack"):
    """A ScanEngine wired the way the CLI wires it: with an analyzer and a finding repository."""
    from ragstrike import PLUGIN_API_VERSION, __version__
    from ragstrike.analyzers.config import build_engine as build_analyzer
    from ragstrike.core.config.models import PluginSettings, Settings, StorageSettings
    from ragstrike.core.orchestrator.scan_engine import ScanEngine
    from ragstrike.database.connection import Database
    from ragstrike.database.migrations.runner import run_migrations
    from ragstrike.database.repositories.finding_repository import FindingRepository
    from ragstrike.database.repositories.scan_repository import ScanRepository
    from ragstrike.database.repositories.target_repository import TargetRepository
    from ragstrike.plugins.registry.plugin_registry import PluginRegistry
    from ragstrike.scheduler.scan_scheduler import ScanScheduler

    database = Database(lab_root / "scans.db")
    await run_migrations(database)
    analyzer, _ = build_analyzer()
    settings = Settings(
        storage=StorageSettings(
            database_path=lab_root / "scans.db", reports_dir=lab_root / "reports"
        ),
        plugins=PluginSettings(local_dirs=[make_plugin(slug)]),
    )
    engine = ScanEngine(
        settings=settings,
        registry=PluginRegistry(settings.plugins, api_version=PLUGIN_API_VERSION),
        scheduler=ScanScheduler(),
        scan_repository=ScanRepository(database),
        target_repository=TargetRepository(database),
        engine_version=__version__,
        analyzer=analyzer,
        finding_repository=FindingRepository(database),
    )
    return engine, FindingRepository(database)


def test_a_scan_produces_and_stores_findings(lab_root, make_plugin) -> None:
    """**The step that was missing for thirteen phases.**

    ``analyzers/`` shipped in Phase 10 and ``reporters/`` in Phase 11, and nothing ever converted a
    ``PluginResult`` into an ``Observation``. The findings table stayed empty, so every report
    scored 0.0 out of 10 and the dashboard showed a grade of "?" for scans that ran perfectly.
    """
    import asyncio

    from tests.conftest import FakeTarget

    from ragstrike.models.entities.target import Authorization, Target

    async def run():
        engine, findings_repo = await _analysing_engine(lab_root, make_plugin)
        target = Target(
            id="t1",
            name="lab",
            adapter="fake",
            url="http://127.0.0.1:9000",
            authorization=Authorization(authorized_by="tester", authorization_ref="LOCAL"),
        )
        outcome = await engine.run(target=target, adapter=FakeTarget())
        stored = await findings_repo.findings_for(outcome.session.id)
        return outcome, stored

    outcome, stored = asyncio.run(run())

    assert outcome.analyzed is True
    assert outcome.findings, "the analyzer produced no findings"
    assert len(stored) == len(outcome.findings), "findings were not persisted"
    assert all(f.scan_id == outcome.session.id for f in stored)


def test_a_scan_without_an_analyzer_says_so_rather_than_reporting_nothing(
    lab_root, make_plugin
) -> None:
    """``analyzed=False`` distinguishes "not analysed" from "analysed and clean".

    Both produce zero findings. Only one of them is a result.
    """
    import asyncio

    from tests.conftest import FakeTarget

    from ragstrike import PLUGIN_API_VERSION, __version__
    from ragstrike.core.config.models import PluginSettings, Settings, StorageSettings
    from ragstrike.core.orchestrator.scan_engine import ScanEngine
    from ragstrike.database.connection import Database
    from ragstrike.database.migrations.runner import run_migrations
    from ragstrike.database.repositories.scan_repository import ScanRepository
    from ragstrike.database.repositories.target_repository import TargetRepository
    from ragstrike.models.entities.target import Authorization, Target
    from ragstrike.plugins.registry.plugin_registry import PluginRegistry
    from ragstrike.scheduler.scan_scheduler import ScanScheduler

    async def run():
        database = Database(lab_root / "plain.db")
        await run_migrations(database)
        settings = Settings(
            storage=StorageSettings(database_path=lab_root / "plain.db"),
            plugins=PluginSettings(local_dirs=[make_plugin("plain-attack")]),
        )
        engine = ScanEngine(
            settings=settings,
            registry=PluginRegistry(settings.plugins, api_version=PLUGIN_API_VERSION),
            scheduler=ScanScheduler(),
            scan_repository=ScanRepository(database),
            target_repository=TargetRepository(database),
            engine_version=__version__,
        )
        target = Target(
            id="t1",
            name="lab",
            adapter="fake",
            url="http://127.0.0.1:9000",
            authorization=Authorization(authorized_by="t", authorization_ref="L"),
        )
        return await engine.run(target=target, adapter=FakeTarget())

    outcome = asyncio.run(run())

    assert outcome.analyzed is False
    assert outcome.findings == []
