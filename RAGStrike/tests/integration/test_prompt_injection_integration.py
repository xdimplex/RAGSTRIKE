"""Phase 7 integration: the real registry, the real scheduler, the real database.

The unit tests reach the pack's methods directly, which proves the detection logic is right but
says nothing about whether the engine can find, validate, schedule, run, and persist it. A pack
whose detectors are perfect and whose manifest is malformed contributes nothing to a scan.

The load-bearing claim tested here is the one the whole plugin architecture rests on: **the engine
runs this pack without knowing anything about it.** No prompt-injection logic exists under
``core/``, and a test in the Phase 3 suite already walks the engine's AST to prove no plugin name
is hardcoded there.
"""

from __future__ import annotations

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
from ragstrike.database.repositories.scan_repository import ScanRepository
from ragstrike.database.repositories.target_repository import TargetRepository
from ragstrike.models.values.enums import Capability, PluginOutcome
from ragstrike.plugins.registry.plugin_registry import PluginRegistry
from ragstrike.scheduler.scan_scheduler import ScanScheduler

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ATTACKS_DIR = REPO_ROOT / "src" / "ragstrike" / "attacks"

SLUG = "prompt-injection"


class LoopbackTarget:
    """A loopback adapter that replies with a fixed string.

    Distinct from ``FakeTarget`` in conftest, which reports ``http://fake`` and is therefore
    refused by this pack -- correctly, and that refusal is itself tested below.
    """

    def __init__(self, reply: str = "The documents cover finance.") -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def describe(self) -> TargetDescriptor:
        return TargetDescriptor(
            adapter="loopback",
            version="1.0.0",
            url="http://127.0.0.1:9000",
            capabilities=(Capability.CHAT,),
        )

    async def health_check(self) -> HealthResult:
        return HealthResult(reachable=True)

    async def close(self) -> None:
        return None

    async def chat(self, request) -> TargetResponse:
        self.prompts.append(request.prompt)
        return TargetResponse(text=self.reply, latency_ms=1)


def attacks_registry() -> PluginRegistry:
    """The first-party attacks directory, discovered exactly as a real run would."""
    return PluginRegistry(PluginSettings(local_dirs=[ATTACKS_DIR]), api_version=PLUGIN_API_VERSION)


async def _result_for(database, scan_id: str):
    """This pack's stored result, selected by slug.

    Every first-party pack in the attacks directory runs in these scans, and results come back in
    slug order -- so positional indexing silently picks a different pack as soon as one is added,
    which is exactly what happened when Phase 9 landed.
    """
    stored = await ScanRepository(database).results_for(scan_id)
    return next(r for r in stored if r.plugin_slug == SLUG)


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


# -- discovery and validation ----------------------------------------------------------------------


def test_the_pack_is_discovered_from_the_first_party_directory() -> None:
    health = attacks_registry().discover()

    assert SLUG in {p.slug for p in health.active}


def test_the_pack_reports_its_real_version_not_a_placeholder() -> None:
    """Discovery reads pack.yaml, so the version is the manifest's rather than the 0.0.0 stub the
    entry-point path synthesizes."""
    registry = attacks_registry()
    registry.discover()

    assert registry.get(SLUG).version == "1.0.0"


def test_the_scaffold_only_packs_are_skipped_without_error() -> None:
    """A pack directory holding only a README must be passed over silently, not rejected --
    Phases 8-10 fill them in, and a rejection list full of unbuilt packs would train an operator
    to ignore it.

    Asserts against the number of directories that actually carry a ``pack.yaml`` rather than
    against a fixed slug set. The original version pinned "exactly prompt-injection", which was
    never the invariant and broke the moment Phase 8 added a second pack.
    """
    health = attacks_registry().discover()
    built = {d.name for d in ATTACKS_DIR.iterdir() if (d / "pack.yaml").is_file()}

    assert health.rejected == [], f"rejected: {[(r.slug, r.reason) for r in health.rejected]}"
    assert len(health.active) == len(
        built
    ), f"built dirs {built} vs active {[p.slug for p in health.active]}"
    assert SLUG in {p.slug for p in health.active}


def test_the_pack_passes_its_own_validation() -> None:
    registry = attacks_registry()
    registry.discover()

    report = registry.get(SLUG).attack.validate()

    assert report.valid, [c.rule for c in report.failures]


def test_the_pack_declares_least_privilege() -> None:
    """It reaches the target only through the injected adapter. Declaring egress it does not use
    would be an unauditable claim."""
    health = attacks_registry().discover()
    manifest = next(p.manifest for p in health.active if p.slug == SLUG)

    assert manifest.permissions.network_egress is False
    assert manifest.permissions.filesystem_write is False


# -- end to end through the engine -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_pack_runs_end_to_end_and_persists(settings, authorized_target) -> None:
    engine, database = await build_engine(settings)

    outcome = await engine.run(target=authorized_target, adapter=LoopbackTarget())

    assert SLUG in {r.plugin_slug for r in outcome.results}

    # Membership, not equality: every first-party pack in the attacks directory runs in this
    # scan, and Phases 8-10 add more of them.
    stored = await ScanRepository(database).results_for(outcome.session.id)
    assert SLUG in {r.plugin_slug for r in stored}


@pytest.mark.asyncio
async def test_a_vulnerable_target_is_recorded_as_failed(settings, authorized_target) -> None:
    engine, _database = await build_engine(settings)

    outcome = await engine.run(
        target=authorized_target, adapter=LoopbackTarget(reply="RAGSTRIKE-PI-Q1")
    )

    result = next(r for r in outcome.results if r.plugin_slug == SLUG)
    assert result.outcome is PluginOutcome.FAIL


@pytest.mark.asyncio
async def test_a_resistant_target_is_recorded_as_passed(settings, authorized_target) -> None:
    engine, _ = await build_engine(settings)

    outcome = await engine.run(
        target=authorized_target, adapter=LoopbackTarget(reply="I cannot comply with that.")
    )

    result = next(r for r in outcome.results if r.plugin_slug == SLUG)
    assert result.outcome is PluginOutcome.PASS


# -- evidence and scan history -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evidence_survives_the_database_round_trip(settings, authorized_target) -> None:
    """Detector signals are the reason a finding is believable. If they do not persist, the report
    can assert a vulnerability but not show its working."""
    engine, database = await build_engine(settings)

    outcome = await engine.run(
        target=authorized_target, adapter=LoopbackTarget(reply="RAGSTRIKE-PI-Q1")
    )

    # Selected by slug, not by position: every first-party pack runs in this scan and results come
    # back in slug order, so index 0 is whichever pack sorts first rather than this one.
    stored = await _result_for(database, outcome.session.id)
    evidence = stored.evidence

    assert evidence.get("signals", {}).get("count", 0) >= 1
    assert any("canary" in item["kind"] for item in evidence["signals"]["items"])


@pytest.mark.asyncio
async def test_the_recommendation_is_stored_with_the_result(settings, authorized_target) -> None:
    engine, database = await build_engine(settings)

    outcome = await engine.run(
        target=authorized_target, adapter=LoopbackTarget(reply="RAGSTRIKE-PI-Q1")
    )

    stored = await _result_for(database, outcome.session.id)
    assert stored.recommendation


@pytest.mark.asyncio
async def test_two_scans_both_appear_in_history(settings, authorized_target) -> None:
    """Scan history is what makes a fix demonstrable: the same pack, the same target, a different
    outcome, both retrievable."""
    engine, database = await build_engine(settings)
    repository = ScanRepository(database)

    vulnerable = await engine.run(
        target=authorized_target, adapter=LoopbackTarget(reply="RAGSTRIKE-PI-Q1")
    )
    fixed = await engine.run(
        target=authorized_target, adapter=LoopbackTarget(reply="I cannot comply.")
    )

    recent = await repository.list_recent(limit=10)
    assert {vulnerable.session.id, fixed.session.id} <= {s.id for s in recent}

    assert (await _result_for(database, vulnerable.session.id)).outcome is PluginOutcome.FAIL
    assert (await _result_for(database, fixed.session.id)).outcome is PluginOutcome.PASS


# -- the engine knows nothing about this pack ----------------------------------------------------------


def test_no_prompt_injection_logic_lives_under_core() -> None:
    """The claim the whole plugin architecture rests on. If this ever fails, the pack has leaked
    into the engine and deleting the pack would break the engine."""
    core = REPO_ROOT / "src" / "ragstrike" / "core"
    offenders = [
        path.relative_to(REPO_ROOT)
        for path in core.rglob("*.py")
        if "canary" in path.read_text(encoding="utf-8").lower()
        or "prompt_injection" in path.read_text(encoding="utf-8").lower()
    ]

    assert offenders == []
