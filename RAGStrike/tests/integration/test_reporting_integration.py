"""Phase 11 integration: a real scan, analyzed, reported, and persisted.

The unit tests exercise the engine against constructed findings. These prove the acceptance
criteria: a real scan's results flow scan -> analyzer -> report -> database, and **no plugin
changed** to make it happen.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from tests.conftest import make_database

from ragstrike import PLUGIN_API_VERSION, __version__
from ragstrike.analyzers.base.observation import Observation
from ragstrike.analyzers.config import build_engine as build_analyzer
from ragstrike.core.config.models import PluginSettings
from ragstrike.core.contracts.target_adapter import (
    HealthResult,
    TargetDescriptor,
    TargetResponse,
)
from ragstrike.core.orchestrator.scan_engine import ScanEngine
from ragstrike.database.migrations.runner import MIGRATIONS
from ragstrike.database.repositories.report_repository import ReportRepository
from ragstrike.database.repositories.scan_repository import ScanRepository
from ragstrike.database.repositories.target_repository import TargetRepository
from ragstrike.models.values.enums import Capability
from ragstrike.plugins.registry.plugin_registry import PluginRegistry
from ragstrike.reporters.base.record import StoredReport
from ragstrike.reporters.base.renderer import ReportRepository as ReportRepositoryPort
from ragstrike.reporters.config import build_service
from ragstrike.scheduler.scan_scheduler import ScanScheduler

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ATTACKS_DIR = REPO_ROOT / "src" / "ragstrike" / "attacks"
ANALYZER_CONFIG = REPO_ROOT / "configs" / "analyzer"
REPORTING_CONFIG = REPO_ROOT / "configs" / "reporting"


class LoopbackTarget:
    """Emits an injection canary, so a real pack produces a real failure to report on."""

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


async def scan_analyze_report(settings, target, *, repository_needed: bool = True):
    """The whole pipeline: scan -> analyze -> report."""
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

    analyzer, _ = build_analyzer(ANALYZER_CONFIG)
    analysis = analyzer.analyze(
        [Observation.from_plugin_result(r, category=r.plugin_slug) for r in stored],
        scan_id=outcome.session.id,
    )

    repository = ReportRepository(database) if repository_needed else None
    service, config, _ = build_service(REPORTING_CONFIG, repository=repository)
    generated = service.generate(
        list(analysis.findings),
        config.context(
            scan_id=outcome.session.id,
            target="http://127.0.0.1:9000",
            framework_version=__version__,
            scan_score=analysis.score.score if analysis.score else 0.0,
        ),
    )
    return database, service, generated, analysis


# -- the migration ------------------------------------------------------------------------------------


def test_the_reports_migration_is_appended_in_order() -> None:
    versions = [version for version, _, _ in MIGRATIONS]

    assert versions == list(range(1, len(versions) + 1))
    assert next(v for v, name, _ in MIGRATIONS if name == "reports") == 4


@pytest.mark.asyncio
async def test_the_report_tables_exist_after_migration(settings) -> None:
    database = await make_database(settings)

    async with database.connect() as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('reports', 'report_exports')"
        )
        assert len({row["name"] for row in await cursor.fetchall()}) == 2


def test_the_repository_satisfies_the_port_reporting_declares() -> None:
    """Conformance by protocol, not inheritance -- reporting cannot import the database."""
    assert issubclass(ReportRepository, ReportRepositoryPort)


# -- the whole pipeline --------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_real_scan_becomes_a_report(settings, authorized_target) -> None:
    """The acceptance criteria in one test."""
    _, _service, generated, analysis = await scan_analyze_report(settings, authorized_target)

    assert generated.model.findings
    assert len(generated.model.findings) == len(analysis.findings)
    assert generated.model.cover.scan_id == analysis.findings[0].scan_id


@pytest.mark.asyncio
async def test_every_section_is_populated_from_a_real_scan(settings, authorized_target) -> None:
    _, _, generated, _ = await scan_analyze_report(settings, authorized_target)
    model = generated.model

    assert model.cover.target
    assert model.summary.status
    assert model.summary.headline
    assert model.categories
    assert model.findings
    assert model.statistics.plugin_count > 0
    assert model.timeline
    assert len(model.charts) == 6


@pytest.mark.asyncio
async def test_a_vulnerable_scan_reports_as_vulnerable(settings, authorized_target) -> None:
    _, _, generated, _ = await scan_analyze_report(settings, authorized_target)

    assert generated.model.summary.status == "VULNERABLE"
    assert generated.model.vulnerabilities


@pytest.mark.asyncio
async def test_all_three_formats_render_from_a_real_scan(settings, authorized_target) -> None:
    _, service, generated, _ = await scan_analyze_report(settings, authorized_target)

    for fmt in ("html", "json", "markdown"):
        assert service.render(generated, fmt).strip(), f"{fmt} rendered nothing"


@pytest.mark.asyncio
async def test_the_formats_agree_about_the_same_scan(settings, authorized_target) -> None:
    """One model, N renderers. If two formats disagreed, a reader would have no way to tell which
    was right."""
    _, service, generated, _ = await scan_analyze_report(settings, authorized_target)

    payload = json.loads(service.render(generated, "json"))
    markdown = service.render(generated, "markdown")

    assert payload["executive_summary"]["status"] in markdown
    assert str(payload["risk_breakdown"]["total"]) in markdown


# -- persistence ------------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_report_persists_and_loads_back(settings, authorized_target) -> None:
    _, service, generated, _ = await scan_analyze_report(settings, authorized_target)

    report_id = await service.store(generated, fmt="html")
    content = await service.load_report(report_id)

    assert content and "<!DOCTYPE html>" in content


@pytest.mark.asyncio
async def test_report_metadata_is_listable(settings, authorized_target) -> None:
    _, service, generated, _ = await scan_analyze_report(settings, authorized_target)
    await service.store(generated, fmt="json")

    listed = await service.list_reports()

    assert len(listed) == 1
    assert listed[0].status == "VULNERABLE"
    assert listed[0].finding_count > 0


@pytest.mark.asyncio
async def test_a_listing_does_not_carry_rendered_content(settings, authorized_target) -> None:
    """Twenty reports in a listing would otherwise mean twenty rendered documents."""
    database, service, generated, _ = await scan_analyze_report(settings, authorized_target)
    await service.store(generated, fmt="html")

    records = await ReportRepository(database).list_reports()

    assert records[0].content == ""


@pytest.mark.asyncio
async def test_deleting_a_report_reports_whether_anything_went(settings, authorized_target) -> None:
    _, service, generated, _ = await scan_analyze_report(settings, authorized_target)
    report_id = await service.store(generated)

    assert await service.delete_report(report_id) is True
    assert await service.delete_report(report_id) is False
    assert await service.list_reports() == []


@pytest.mark.asyncio
async def test_exporting_records_history(settings, authorized_target, tmp_path) -> None:
    database, service, generated, _ = await scan_analyze_report(settings, authorized_target)
    report_id = await service.store(generated)

    record = await service.export(generated, "markdown", output_dir=tmp_path)

    assert record.path.is_file()
    exports = await ReportRepository(database).exports_for(report_id)
    assert [e["format"] for e in exports] == ["markdown"]


@pytest.mark.asyncio
async def test_the_stored_content_is_what_was_rendered(settings, authorized_target) -> None:
    """A report is the record of what was actually shown, not a recipe for rebuilding something
    similar."""
    _, service, generated, _ = await scan_analyze_report(settings, authorized_target)

    rendered = service.render(generated, "markdown")
    report_id = await service.store(generated, fmt="markdown")

    assert await service.load_report(report_id) == rendered


@pytest.mark.asyncio
async def test_reports_are_scoped_by_scan(settings, authorized_target) -> None:
    _, service, generated, _ = await scan_analyze_report(settings, authorized_target)
    await service.store(generated)

    assert await service.list_reports(generated.scan_id)
    assert await service.list_reports("a-different-scan") == []


@pytest.mark.asyncio
async def test_a_stored_report_carries_its_versions(settings, authorized_target) -> None:
    """A stored report is only interpretable against the shape and rules that produced it."""
    database, service, generated, _ = await scan_analyze_report(settings, authorized_target)
    report_id = await service.store(generated)

    record = await ReportRepository(database).load_report(report_id)

    assert record is not None
    assert record.report_version
    assert record.analyzer_version
    assert record.framework_version


# -- no plugin changed ---------------------------------------------------------------------------------------------


def test_no_pack_imports_the_reporting_engine() -> None:
    """The acceptance criterion "require no changes to existing plugins", enforced. A pack importing
    the reporter would mean the packs had been adapted to it rather than the reverse."""
    offenders = [
        path.relative_to(REPO_ROOT)
        for path in ATTACKS_DIR.rglob("*.py")
        if "ragstrike.reporters" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def test_reporting_never_imports_the_database() -> None:
    """Including from inside a function. grimp reads the whole AST, so a deferred import is the
    same dependency -- this caught a real violation during Phase 11."""
    reporters = REPO_ROOT / "src" / "ragstrike" / "reporters"

    offenders = [
        (path.relative_to(REPO_ROOT), module)
        for path in reporters.rglob("*.py")
        for module in _imported_modules(path)
        if module.startswith("ragstrike.database")
    ]

    assert offenders == []


def test_reporting_imports_no_pack_or_plugin() -> None:
    reporters = REPO_ROOT / "src" / "ragstrike" / "reporters"

    offenders = [
        (path.relative_to(REPO_ROOT), module)
        for path in reporters.rglob("*.py")
        for module in _imported_modules(path)
        if module.startswith(("ragstrike.attacks", "ragstrike.plugins"))
    ]

    assert offenders == []


def test_the_analyzer_never_imports_the_reporter() -> None:
    """The dependency is one-directional: reporting reads findings, and the analyzer must never
    know a report exists."""
    analyzers = REPO_ROOT / "src" / "ragstrike" / "analyzers"

    offenders = [
        (path.relative_to(REPO_ROOT), module)
        for path in analyzers.rglob("*.py")
        for module in _imported_modules(path)
        if module.startswith("ragstrike.reporters")
    ]

    assert offenders == []


def test_the_persistence_payload_is_owned_by_reporting() -> None:
    """StoredReport lives on the lower layer so the database maps it, rather than reporting
    importing a database type."""
    assert StoredReport.__module__.startswith("ragstrike.reporters")
