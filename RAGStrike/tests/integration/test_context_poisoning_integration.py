"""Phase 9 integration: the real registry, scheduler, engine, and database.

The acceptance criteria the phase states are claims about the *system*, not the plugin: the pack is
discovered automatically, no Scan Engine change is required, results reach the database, and scan
history accumulates. Those are what this file asserts.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.conftest import make_database

from ragstrike import PLUGIN_API_VERSION, __version__
from ragstrike.core.config.models import PluginSettings
from ragstrike.core.contracts.target_adapter import (
    HealthResult,
    TargetDescriptor,
    TargetResponse,
)
from ragstrike.core.orchestrator.scan_engine import ScanEngine
from ragstrike.database.repositories.plugin_repository import PluginRepository
from ragstrike.database.repositories.scan_repository import ScanRepository
from ragstrike.database.repositories.target_repository import TargetRepository
from ragstrike.models.values.enums import Capability, PluginOutcome
from ragstrike.plugins.registry.plugin_registry import PluginRegistry
from ragstrike.scheduler.scan_scheduler import ScanScheduler

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ATTACKS_DIR = REPO_ROOT / "src" / "ragstrike" / "attacks"

SLUG = "context-poisoning"
BENIGN = ["company_handbook.pdf", "policy_document.pdf", "product_faq.pdf"]
POISON = "hidden_instruction.pdf"


class LoopbackTarget:
    def __init__(self, sources: list[str] | None = None, text: str = "An answer.") -> None:
        self.sources = BENIGN if sources is None else sources
        self.text = text

    def describe(self) -> TargetDescriptor:
        return TargetDescriptor(
            adapter="loopback",
            version="1.0.0",
            url="http://127.0.0.1:9000",
            capabilities=(Capability.CHAT, Capability.RETURN_CHUNKS),
        )

    async def health_check(self) -> HealthResult:
        return HealthResult(reachable=True)

    async def close(self) -> None:
        return None

    async def chat(self, request) -> TargetResponse:
        chunks = [{"chunk_id": f"c{i}", "source_name": s} for i, s in enumerate(self.sources)]
        return TargetResponse(
            text=self.text, retrieved_chunks=chunks, sources=self.sources, latency_ms=5
        )


def attacks_registry() -> PluginRegistry:
    return PluginRegistry(PluginSettings(local_dirs=[ATTACKS_DIR]), api_version=PLUGIN_API_VERSION)


async def build_engine(settings):
    database = await make_database(settings)
    engine = ScanEngine(
        settings=settings,
        registry=attacks_registry(),
        scheduler=ScanScheduler(),
        scan_repository=ScanRepository(database),
        target_repository=TargetRepository(database),
        engine_version=__version__,
    )
    return engine, database


async def result_for(database, scan_id: str):
    stored = await ScanRepository(database).results_for(scan_id)
    return next(r for r in stored if r.plugin_slug == SLUG)


# -- automatic discovery ------------------------------------------------------------------------------


def test_the_pack_is_discovered_automatically() -> None:
    """An acceptance criterion verbatim: discoverable through the existing plugin framework, with
    no registration step anywhere."""
    assert SLUG in {p.slug for p in attacks_registry().discover().active}


def test_the_pack_reports_its_real_version() -> None:
    registry = attacks_registry()
    registry.discover()

    assert registry.get(SLUG).version == "1.0.0"


def test_no_pack_is_rejected() -> None:
    health = attacks_registry().discover()

    assert health.rejected == [], f"rejected: {[(r.slug, r.reason) for r in health.rejected]}"


def test_the_pack_passes_validation_through_the_registry() -> None:
    registry = attacks_registry()
    registry.discover()

    report = registry.get(SLUG).attack.validate()

    assert report.valid, [c.rule for c in report.failures]


def test_all_three_first_party_packs_coexist() -> None:
    active = {p.slug for p in attacks_registry().discover().active}

    assert {"prompt-injection", "prompt-leakage", "context-poisoning"} <= active


def test_the_pack_declares_least_privilege() -> None:
    health = attacks_registry().discover()
    manifest = next(p.manifest for p in health.active if p.slug == SLUG)

    assert manifest.permissions.network_egress is False
    assert manifest.permissions.filesystem_write is False


# -- end to end, with no engine change --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_pack_runs_end_to_end_and_persists(settings, authorized_target) -> None:
    engine, database = await build_engine(settings)

    outcome = await engine.run(target=authorized_target, adapter=LoopbackTarget())

    stored = await result_for(database, outcome.session.id)
    assert stored.plugin_slug == SLUG


@pytest.mark.asyncio
async def test_a_healthy_corpus_is_recorded_as_passed(settings, authorized_target) -> None:
    engine, database = await build_engine(settings)

    outcome = await engine.run(target=authorized_target, adapter=LoopbackTarget())

    assert (await result_for(database, outcome.session.id)).outcome is PluginOutcome.PASS


@pytest.mark.asyncio
async def test_a_poisoned_retrieval_is_recorded_as_failed(settings, authorized_target) -> None:
    engine, database = await build_engine(settings)

    outcome = await engine.run(target=authorized_target, adapter=LoopbackTarget([*BENIGN, POISON]))

    stored = await result_for(database, outcome.session.id)
    assert stored.outcome is PluginOutcome.FAIL
    assert stored.recommendation


# -- the reporting contract -----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_every_reporting_field_survives_the_database_round_trip(
    settings, authorized_target
) -> None:
    """The nine fields the brief names, read back from storage rather than from memory."""
    engine, database = await build_engine(settings)

    outcome = await engine.run(target=authorized_target, adapter=LoopbackTarget([*BENIGN, POISON]))
    stored = await result_for(database, outcome.session.id)

    assert stored.scan_id == outcome.session.id  # scan id
    assert stored.plugin_slug == SLUG  # plugin id
    assert stored.created_at is not None  # timestamp
    assert stored.elapsed_ms >= 0  # execution duration
    assert stored.outcome is not None  # status
    assert stored.evidence  # evidence
    assert stored.recommendation  # recommendation
    assert "confidence" in stored.evidence  # confidence
    # evaluation id and target, per case
    assert all(r["evidence"]["question_id"] for r in stored.evidence["results"])
    assert all(r["target"] for r in stored.evidence["results"])


@pytest.mark.asyncio
async def test_the_dataset_version_is_persisted(settings, authorized_target) -> None:
    """A result is only interpretable against the dataset that produced it, so the version has to
    survive into storage -- otherwise a re-run against an edited dataset is silently incomparable.
    """
    engine, database = await build_engine(settings)

    outcome = await engine.run(target=authorized_target, adapter=LoopbackTarget())
    stored = await result_for(database, outcome.session.id)

    assert stored.evidence["datasets"]
    assert all(d["dataset_version"] for d in stored.evidence["datasets"])
    assert all(r["evidence"]["dataset_version"] for r in stored.evidence["results"])


@pytest.mark.asyncio
async def test_the_analyzer_reason_is_persisted(settings, authorized_target) -> None:
    """Remediation is keyed by reason, so a stored result has to carry it or the advice cannot be
    reproduced from history."""
    engine, database = await build_engine(settings)

    outcome = await engine.run(target=authorized_target, adapter=LoopbackTarget([*BENIGN, POISON]))
    stored = await result_for(database, outcome.session.id)

    assert "forbidden_source_retrieved" in stored.detail
    assert any(
        r["evidence"].get("reason") == "forbidden_source_retrieved"
        for r in stored.evidence["results"]
    )


@pytest.mark.asyncio
async def test_evidence_is_storable_json(settings, authorized_target) -> None:
    engine, database = await build_engine(settings)

    outcome = await engine.run(target=authorized_target, adapter=LoopbackTarget())

    json.dumps((await result_for(database, outcome.session.id)).evidence)


# -- history and statistics -------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluation_history_accumulates(settings, authorized_target) -> None:
    engine, database = await build_engine(settings)
    repository = ScanRepository(database)

    poisoned = await engine.run(target=authorized_target, adapter=LoopbackTarget([*BENIGN, POISON]))
    clean = await engine.run(target=authorized_target, adapter=LoopbackTarget())

    recent = await repository.list_recent(limit=10)
    assert {poisoned.session.id, clean.session.id} <= {s.id for s in recent}

    assert (await result_for(database, poisoned.session.id)).outcome is PluginOutcome.FAIL
    assert (await result_for(database, clean.session.id)).outcome is PluginOutcome.PASS


@pytest.mark.asyncio
async def test_plugin_execution_statistics_count_this_pack(settings, authorized_target) -> None:
    engine, database = await build_engine(settings)

    await engine.run(target=authorized_target, adapter=LoopbackTarget())
    await engine.run(target=authorized_target, adapter=LoopbackTarget([*BENIGN, POISON]))

    stats = {s.slug: s for s in await PluginRepository(database).statistics()}

    assert stats[SLUG].total_runs == 2
    assert stats[SLUG].passed == 1
    assert stats[SLUG].failed == 1


@pytest.mark.asyncio
async def test_execution_duration_is_recorded_per_case(settings, authorized_target) -> None:
    engine, database = await build_engine(settings)

    outcome = await engine.run(target=authorized_target, adapter=LoopbackTarget())
    stored = await result_for(database, outcome.session.id)

    assert all("execution_ms" in r["evidence"] for r in stored.evidence["results"])


# -- the engine knows nothing about this pack -------------------------------------------------------------------------


def test_no_context_poisoning_logic_lives_under_core() -> None:
    """An acceptance criterion verbatim: no changes required in the Scan Engine."""
    core = REPO_ROOT / "src" / "ragstrike" / "core"
    offenders = [
        path.relative_to(REPO_ROOT)
        for path in core.rglob("*.py")
        if "context_poisoning" in path.read_text(encoding="utf-8").lower()
        or "dataset_id" in path.read_text(encoding="utf-8").lower()
    ]

    assert offenders == []
