"""Phase 10 integration: real migrations, real database, real packs.

The unit tests exercise the engine against constructed observations. These prove the thing that
actually matters for the acceptance criteria: a real scan's stored results flow into the analyzer,
become findings, and persist -- **with no change to any plugin**.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from tests.conftest import make_database

from ragstrike import PLUGIN_API_VERSION, __version__
from ragstrike.analyzers.base.observation import Observation
from ragstrike.analyzers.base.ports import FindingRepository as FindingRepositoryPort
from ragstrike.analyzers.config import build_engine
from ragstrike.core.config.models import PluginSettings
from ragstrike.core.contracts.target_adapter import (
    HealthResult,
    TargetDescriptor,
    TargetResponse,
)
from ragstrike.core.orchestrator.scan_engine import ScanEngine
from ragstrike.database.migrations.runner import MIGRATIONS
from ragstrike.database.repositories.finding_repository import FindingRepository
from ragstrike.database.repositories.scan_repository import ScanRepository
from ragstrike.database.repositories.target_repository import TargetRepository
from ragstrike.models.values.enums import Capability, PluginOutcome
from ragstrike.plugins.registry.plugin_registry import PluginRegistry
from ragstrike.scheduler.scan_scheduler import ScanScheduler

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ATTACKS_DIR = REPO_ROOT / "src" / "ragstrike" / "attacks"
CONFIG_DIR = REPO_ROOT / "configs" / "analyzer"


class LoopbackTarget:
    """A loopback target that emits an injection canary, so a real pack produces a real failure."""

    def __init__(self, reply: str = "RAGSTRIKE-PI-Q1") -> None:
        self.reply = reply

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
        return TargetResponse(
            text=self.reply,
            retrieved_chunks=[{"chunk_id": "c0", "source_name": "company_handbook.pdf"}],
            sources=["company_handbook.pdf"],
            latency_ms=5,
        )


async def run_scan(settings, target):
    """Run a real scan over the shipped first-party packs and return its stored results."""
    database = await make_database(settings)
    engine = ScanEngine(
        settings=settings,
        registry=PluginRegistry(
            PluginSettings(local_dirs=[ATTACKS_DIR]), api_version=PLUGIN_API_VERSION
        ),
        scheduler=ScanScheduler(),
        scan_repository=ScanRepository(database),
        target_repository=TargetRepository(database),
        engine_version=__version__,
    )
    outcome = await engine.run(target=target, adapter=LoopbackTarget())
    stored = await ScanRepository(database).results_for(outcome.session.id)
    return database, outcome, stored


# -- the migration ------------------------------------------------------------------------------------


def test_the_findings_migration_is_appended_not_inserted() -> None:
    """Migration ledgers are ordered by version; inserting between released numbers would silently
    reapply already-recorded work.

    Asserts the ordering invariant rather than a fixed latest version. The original pinned
    ``versions[-1] == 3``, which was never the property that mattered and broke the moment Phase 11
    appended migration 4.
    """
    versions = [version for version, _, _ in MIGRATIONS]

    assert versions == sorted(versions), "migrations are out of order"
    assert versions == list(range(1, len(versions) + 1)), "migration versions have a gap"
    assert len(versions) == len(set(versions)), "duplicate migration version"

    findings_migration = next(v for v, name, _ in MIGRATIONS if name == "analyzer_findings")
    assert findings_migration == 3


@pytest.mark.asyncio
async def test_the_findings_table_exists_after_migration(settings) -> None:
    database = await make_database(settings)

    async with database.connect() as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='findings'"
        )
        assert await cursor.fetchone() is not None


def test_the_repository_satisfies_the_port_the_analyzer_declares() -> None:
    """The engine cannot import a repository -- database sits above analyzers in the layer
    contract -- so conformance is by protocol rather than by inheritance."""
    assert issubclass(FindingRepository, FindingRepositoryPort)


# -- a real scan becomes findings ------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stored_plugin_results_become_findings(settings, authorized_target) -> None:
    """The acceptance criterion in one test: real results in, standardized findings out, no plugin
    touched."""
    _database, outcome, stored = await run_scan(settings, authorized_target)
    assert stored, "the scan produced no plugin results"

    analyzer, _ = build_engine(CONFIG_DIR)
    observations = [Observation.from_plugin_result(r, category=r.plugin_slug) for r in stored]

    report = analyzer.analyze(observations, scan_id=outcome.session.id)

    assert len(report.findings) == len(stored)
    assert all(f.scan_id == outcome.session.id for f in report.findings)


@pytest.mark.asyncio
async def test_findings_persist_and_read_back(settings, authorized_target) -> None:
    database, outcome, stored = await run_scan(settings, authorized_target)
    analyzer, _ = build_engine(CONFIG_DIR)
    repository = FindingRepository(database)
    observations = [Observation.from_plugin_result(r, category=r.plugin_slug) for r in stored]

    report = await analyzer.analyze_and_store(observations, repository, scan_id=outcome.session.id)

    read_back = await repository.findings_for(outcome.session.id)
    assert len(read_back) == len(report.findings)
    assert {f.id for f in read_back} == {f.id for f in report.findings}


@pytest.mark.asyncio
async def test_every_finding_field_survives_the_round_trip(settings, authorized_target) -> None:
    database, outcome, stored = await run_scan(settings, authorized_target)
    analyzer, _ = build_engine(CONFIG_DIR)
    repository = FindingRepository(database)
    observations = [Observation.from_plugin_result(r, category=r.plugin_slug) for r in stored]

    await analyzer.analyze_and_store(observations, repository, scan_id=outcome.session.id)
    finding = (await repository.findings_for(outcome.session.id))[0]

    assert finding.id
    assert finding.scan_id == outcome.session.id
    assert finding.plugin_id
    assert finding.status is not None
    assert finding.severity is not None
    assert finding.analyzer_version  # analyzer version
    assert finding.timestamp is not None  # timestamp
    assert isinstance(finding.evidence, dict)  # evidence
    assert isinstance(finding.confidence, float)
    assert isinstance(finding.risk_score, float)


@pytest.mark.asyncio
async def test_scores_and_confidence_persist(settings, authorized_target) -> None:
    """Scores and confidence are the numbers a report leads with. If they do not survive storage,
    the report has to recompute them and can silently disagree with what was analyzed."""
    database, outcome, stored = await run_scan(settings, authorized_target)
    analyzer, _ = build_engine(CONFIG_DIR)
    repository = FindingRepository(database)
    observations = [Observation.from_plugin_result(r, category=r.plugin_slug) for r in stored]

    report = await analyzer.analyze_and_store(observations, repository, scan_id=outcome.session.id)
    read_back = await repository.findings_for(outcome.session.id)

    by_id = {f.id: f for f in read_back}
    for original in report.findings:
        stored_finding = by_id[original.id]
        assert stored_finding.confidence == pytest.approx(original.confidence, abs=0.0001)
        assert stored_finding.risk_score == pytest.approx(original.risk_score, abs=0.01)
        assert stored_finding.confidence_band == original.confidence_band


@pytest.mark.asyncio
async def test_recommendations_persist(settings, authorized_target) -> None:
    database, outcome, stored = await run_scan(settings, authorized_target)
    analyzer, _ = build_engine(CONFIG_DIR)
    repository = FindingRepository(database)
    observations = [Observation.from_plugin_result(r, category=r.plugin_slug) for r in stored]

    await analyzer.analyze_and_store(observations, repository, scan_id=outcome.session.id)

    assert all(f.recommendation for f in await repository.findings_for(outcome.session.id))


@pytest.mark.asyncio
async def test_finding_counts_are_queryable(settings, authorized_target) -> None:
    database, outcome, stored = await run_scan(settings, authorized_target)
    analyzer, _ = build_engine(CONFIG_DIR)
    repository = FindingRepository(database)
    observations = [Observation.from_plugin_result(r, category=r.plugin_slug) for r in stored]

    await analyzer.analyze_and_store(observations, repository, scan_id=outcome.session.id)

    counts = await repository.count_for(outcome.session.id)
    assert set(counts) == {o.value for o in PluginOutcome}
    assert sum(counts.values()) == len(stored)


@pytest.mark.asyncio
async def test_evidence_survives_as_structured_json(settings, authorized_target) -> None:
    database, outcome, stored = await run_scan(settings, authorized_target)
    analyzer, _ = build_engine(CONFIG_DIR)
    repository = FindingRepository(database)
    observations = [Observation.from_plugin_result(r, category=r.plugin_slug) for r in stored]

    await analyzer.analyze_and_store(observations, repository, scan_id=outcome.session.id)
    finding = (await repository.findings_for(outcome.session.id))[0]

    json.dumps(finding.evidence)
    assert "timing" in finding.evidence


# -- findings are separate from observations -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_re_analysis_does_not_rewrite_the_observations(settings, authorized_target) -> None:
    """Findings are stored separately from plugin_results on purpose: rules change, so the same
    observations can be re-graded later without rewriting the record of what actually happened."""
    database, outcome, stored = await run_scan(settings, authorized_target)
    analyzer, _ = build_engine(CONFIG_DIR)
    repository = FindingRepository(database)
    observations = [Observation.from_plugin_result(r, category=r.plugin_slug) for r in stored]

    await analyzer.analyze_and_store(observations, repository, scan_id=outcome.session.id)
    await analyzer.analyze_and_store(observations, repository, scan_id=outcome.session.id)

    # Plugin results are untouched; findings accumulated.
    assert len(await ScanRepository(database).results_for(outcome.session.id)) == len(stored)
    assert len(await repository.findings_for(outcome.session.id)) == len(stored) * 2


@pytest.mark.asyncio
async def test_vulnerabilities_exclude_undetermined_results(settings, authorized_target) -> None:
    """An undetermined result is not evidence of weakness any more than of strength."""
    database, outcome, stored = await run_scan(settings, authorized_target)
    analyzer, _ = build_engine(CONFIG_DIR)
    repository = FindingRepository(database)
    observations = [Observation.from_plugin_result(r, category=r.plugin_slug) for r in stored]

    await analyzer.analyze_and_store(observations, repository, scan_id=outcome.session.id)

    assert all(
        f.status is PluginOutcome.FAIL
        for f in await repository.vulnerabilities_for(outcome.session.id)
    )


# -- no plugin changed --------------------------------------------------------------------------------------------


def test_no_analyzer_import_exists_in_any_pack() -> None:
    """The acceptance criterion "require no changes to existing plugins", enforced. A pack importing
    the analyzer would mean the packs had been adapted to it rather than the reverse."""
    offenders = [
        path.relative_to(REPO_ROOT)
        for path in ATTACKS_DIR.rglob("*.py")
        if "ragstrike.analyzers" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def _code_strings(path: Path) -> list[str]:
    """String literals in *path* that are not docstrings.

    Grepping the raw file would match prose -- a docstring explaining why the analyzer does not
    import the database contains the very substring such a test looks for. Parsing and excluding
    docstrings checks what the code actually does, which is the property being asserted.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        ast.get_docstring(node, clean=False)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value not in docstrings
    ]


def _imported_modules(path: Path) -> list[str]:
    """Modules *path* actually imports, from the AST rather than from text."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def test_the_analyzer_names_no_plugin() -> None:
    """The engine must be completely independent of any specific plugin.

    Checks string literals in code, not prose: rules.yaml legitimately names categories -- that is
    configuration -- and a docstring may use one as an example. What must not exist is analyzer
    code branching on a plugin or category name.
    """
    analyzers_dir = REPO_ROOT / "src" / "ragstrike" / "analyzers"
    forbidden = {"prompt_injection", "prompt_leakage", "context_poisoning", "prompt-injection"}

    offenders = [
        (path.relative_to(REPO_ROOT), literal)
        for path in analyzers_dir.rglob("*.py")
        for literal in _code_strings(path)
        if literal.lower() in forbidden
    ]

    assert offenders == []


def test_the_analyzer_never_imports_the_database() -> None:
    """Analysis is a pure transformation. Depending on SQLite would mean the engine could only be
    tested with a database attached -- and lint-imports enforces the same rule structurally."""
    analyzers_dir = REPO_ROOT / "src" / "ragstrike" / "analyzers"

    offenders = [
        (path.relative_to(REPO_ROOT), module)
        for path in analyzers_dir.rglob("*.py")
        for module in _imported_modules(path)
        if module.startswith("ragstrike.database")
    ]

    assert offenders == []


def test_the_analyzer_imports_no_pack() -> None:
    """The same independence, from the other direction."""
    analyzers_dir = REPO_ROOT / "src" / "ragstrike" / "analyzers"

    offenders = [
        (path.relative_to(REPO_ROOT), module)
        for path in analyzers_dir.rglob("*.py")
        for module in _imported_modules(path)
        if module.startswith(("ragstrike.attacks", "ragstrike.plugins"))
    ]

    assert offenders == []
