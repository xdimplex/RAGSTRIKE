"""Phase 6 integration: the real registry, the real loader, the real database.

Nothing is stubbed except the target. These tests exist because the unit tests reach ``judge()``
directly, which proves the criteria are right but says nothing about whether the five plugins are
*discoverable, loadable, and schedulable* by the machinery that will actually run them. A plugin
whose criterion is perfect and whose manifest is malformed contributes nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.conftest import FakeTarget, make_database

from ragstrike import PLUGIN_API_VERSION, __version__
from ragstrike.core.config.models import PluginSettings
from ragstrike.core.orchestrator.scan_engine import ScanEngine
from ragstrike.database.repositories.plugin_repository import PluginRepository
from ragstrike.database.repositories.scan_repository import ScanRepository
from ragstrike.database.repositories.target_repository import TargetRepository
from ragstrike.models.entities.scan import PluginResult, ScanSession
from ragstrike.models.values.enums import PluginOutcome
from ragstrike.plugins.registry.plugin_registry import PluginRegistry
from ragstrike.scheduler.scan_scheduler import ScanScheduler

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGINS_DIR = REPO_ROOT / "plugins"

EVALUATION_SLUGS = {
    "instruction-priority",
    "prompt-boundary",
    "context-separation",
    "source-attribution",
    "retrieval-consistency",
}


def real_registry() -> PluginRegistry:
    """The shipped plugins directory, discovered exactly as a real run would."""
    return PluginRegistry(PluginSettings(local_dirs=[PLUGINS_DIR]), api_version=PLUGIN_API_VERSION)


# -- discovery and validation ----------------------------------------------------------------------


def test_all_five_evaluation_plugins_are_discovered() -> None:
    health = real_registry().discover()

    assert {p.slug for p in health.active} >= EVALUATION_SLUGS


def test_no_shipped_plugin_is_rejected() -> None:
    """A rejected plugin is invisible at scan time, so a manifest typo would otherwise show up as
    a quietly smaller report rather than an error."""
    health = real_registry().discover()

    assert health.rejected == [], f"rejected: {[(r.slug, r.reason) for r in health.rejected]}"


def test_every_evaluation_plugin_passes_its_own_validation() -> None:
    registry = real_registry()
    registry.discover()

    for slug in sorted(EVALUATION_SLUGS):
        loaded = registry.get(slug)
        assert loaded is not None, f"{slug} was not loaded"
        report = loaded.attack.validate()
        assert report.valid, f"{slug} failed validation: {[c.rule for c in report.failures]}"


def test_every_evaluation_plugin_declares_least_privilege() -> None:
    """These plugins reach the target only through the injected adapter. A manifest asking for
    raw egress or filesystem writes would be claiming capability it does not use."""
    health = real_registry().discover()

    for plugin in health.active:
        if plugin.slug in EVALUATION_SLUGS:
            assert plugin.manifest.permissions.network_egress is False
            assert plugin.manifest.permissions.filesystem_write is False


def test_every_evaluation_plugin_ships_its_test_cases() -> None:
    registry = real_registry()
    registry.discover()

    for slug in sorted(EVALUATION_SLUGS):
        loaded = registry.get(slug)
        assert loaded is not None, f"{slug} was not loaded"
        assert loaded.attack.payloads(), f"{slug} shipped no test cases"


# -- end to end through the scheduler ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_evaluation_plugins_run_end_to_end_against_a_fake_target(
    settings, authorized_target
) -> None:
    """The whole path: discover, schedule, execute, analyze, persist -- with zero engine edits."""
    database = await make_database(settings)
    engine = ScanEngine(
        settings=settings,
        registry=real_registry(),
        scheduler=ScanScheduler(),
        scan_repository=ScanRepository(database),
        target_repository=TargetRepository(database),
        engine_version=__version__,
    )

    outcome = await engine.run(
        target=authorized_target,
        adapter=FakeTarget(reply="The documents cover quarterly finance reporting."),
    )

    ran = {r.plugin_slug for r in outcome.results}
    assert ran >= EVALUATION_SLUGS


@pytest.mark.asyncio
async def test_a_clean_target_produces_no_vulnerability_findings(
    settings, authorized_target
) -> None:
    """A reply that echoes no marker and leaks no configuration must not be graded as vulnerable.

    Source attribution and retrieval consistency are excluded: FakeTarget returns no chunks, so
    those two legitimately cannot reach a verdict here. That they report something *other* than
    PASS is the point -- absent evidence is not a clean bill of health.
    """
    database = await make_database(settings)
    engine = ScanEngine(
        settings=settings,
        registry=real_registry(),
        scheduler=ScanScheduler(),
        scan_repository=ScanRepository(database),
        target_repository=TargetRepository(database),
        engine_version=__version__,
    )

    outcome = await engine.run(
        target=authorized_target,
        adapter=FakeTarget(reply="The documents cover quarterly finance reporting."),
    )

    text_criteria = {"instruction-priority", "prompt-boundary", "context-separation"}
    for result in outcome.results:
        if result.plugin_slug in text_criteria:
            assert result.outcome is PluginOutcome.PASS, f"{result.plugin_slug}: {result.summary}"


# -- INCONCLUSIVE survives a database round trip ------------------------------------------------------


async def seeded_scan(settings, authorized_target, outcomes: list[PluginOutcome]):
    """A persisted scan carrying one result per entry in *outcomes*."""
    database = await make_database(settings)
    repository = ScanRepository(database)

    session = ScanSession(
        id=ScanSession.new_id(),
        target_id=authorized_target.id,
        target_name=authorized_target.name,
        engine_version=__version__,
    )
    await repository.create(session, config_snapshot={})
    await repository.add_results(
        [
            PluginResult(
                id=PluginResult.new_id(),
                scan_id=session.id,
                plugin_slug="instruction-priority",
                plugin_version="1.0.0",
                outcome=outcome,
                summary="seeded",
            )
            for outcome in outcomes
        ]
    )
    return database, repository, session


@pytest.mark.asyncio
async def test_inconclusive_persists_and_reads_back(settings, authorized_target) -> None:
    """``outcome`` is plain TEXT with no CHECK constraint, which is why the new value needed no
    migration -- but "needed no migration" is a claim worth testing rather than asserting."""
    _database, repository, session = await seeded_scan(
        settings, authorized_target, [PluginOutcome.INCONCLUSIVE]
    )

    stored = await repository.results_for(session.id)

    assert [r.outcome for r in stored] == [PluginOutcome.INCONCLUSIVE]


@pytest.mark.asyncio
async def test_statistics_count_inconclusive_separately_from_errors(
    settings, authorized_target
) -> None:
    """An undetermined result and a broken one need different follow-up, so they must not share a
    column."""
    database, _, _ = await seeded_scan(
        settings,
        authorized_target,
        [PluginOutcome.INCONCLUSIVE, PluginOutcome.INCONCLUSIVE, PluginOutcome.ERROR],
    )

    stats = {s.slug: s for s in await PluginRepository(database).statistics()}

    assert stats["instruction-priority"].inconclusive == 2
    assert stats["instruction-priority"].errored == 1
