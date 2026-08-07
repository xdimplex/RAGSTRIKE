"""Engine, registry, exporter, service, and configuration tests.

The claim under test: **adding a format changes no existing code.** If the registry, the engine, or
the exporter names a format anywhere, the Open/Closed requirement is decorative.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from ragstrike.analyzers.base.finding import Finding
from ragstrike.models.values.enums import PluginOutcome, Severity
from ragstrike.reporters.base.renderer import BaseRenderer
from ragstrike.reporters.builders.report_builder import ReportContext
from ragstrike.reporters.config import build_service, load_config
from ragstrike.reporters.engine.report_engine import (
    ReportEngine,
    ReportRegistry,
    UnknownFormatError,
    context_from,
    default_registry,
)
from ragstrike.reporters.exporters.export_manager import ExportManager, safe_component
from ragstrike.reporters.models.report import ReportModel
from ragstrike.reporters.service import ReportService
from ragstrike.reporters.validators.report_validator import ReportValidationError

SHIPPED = Path("configs") / "reporting"
NOW = datetime(2026, 7, 30, 12, 0, 0, tzinfo=UTC)


def finding(**kwargs) -> Finding:
    defaults = {
        "id": "f1",
        "scan_id": "s1",
        "plugin_id": "prompt-injection",
        "category": "prompt_injection",
        "status": PluginOutcome.FAIL,
        "severity": Severity.HIGH,
        "confidence": 0.9,
        "risk_score": 7.2,
        "timestamp": NOW,
        "analyzer_version": "1.0.0",
        "recommendation": "Separate instructions from data",
        "evidence": {"summary": "found"},
        "metadata": {"execution_ms": 120},
    }
    defaults.update(kwargs)
    return Finding(**defaults)


class CsvRenderer(BaseRenderer):
    """A format the engine has never heard of. Proves the extension point."""

    name = "csv"
    extension = "csv"
    media_type = "text/csv"

    def render(self, report: ReportModel) -> str:
        rows = ["plugin,severity,status"]
        rows += [f"{f.plugin},{f.severity},{f.status}" for f in report.findings]
        return "\n".join(rows)


# -- registry ------------------------------------------------------------------------------------------


def test_the_default_registry_has_the_shipped_formats() -> None:
    assert set(default_registry().names()) == {"html", "json", "markdown", "pdf"}


def test_available_tracks_what_can_actually_render() -> None:
    """``available()`` is the set a caller can safely ask for.

    Every shipped format is now implemented -- PDF stopped being a placeholder in Phase 16 -- so this
    asserts the two sets agree rather than asserting a specific absence. Written this way it keeps
    working when a future format arrives declared-but-unbuilt, which is the case it exists for.
    """
    registry = default_registry()

    assert set(registry.available()) == {
        name for name in registry.names() if registry.get(name).implemented
    }
    assert "pdf" in registry.available()


def test_an_unknown_format_raises_with_the_alternatives() -> None:
    with pytest.raises(UnknownFormatError) as excinfo:
        default_registry().get("xml")

    assert "html" in excinfo.value.hint


def test_a_duplicate_name_is_refused() -> None:
    """Silently overwriting would make "which renderer produced this" depend on import order."""
    registry = ReportRegistry()
    registry.register(CsvRenderer())

    with pytest.raises(ValueError, match="already registered"):
        registry.register(CsvRenderer())


def test_a_duplicate_can_be_replaced_deliberately() -> None:
    registry = ReportRegistry()
    registry.register(CsvRenderer())
    registry.register(CsvRenderer(), replace=True)

    assert len(registry) == 1


def test_an_unnamed_renderer_is_refused() -> None:
    class Nameless(BaseRenderer):
        name = ""

        def render(self, report: ReportModel) -> str:  # pragma: no cover
            return ""

    with pytest.raises(ValueError, match="non-empty name"):
        ReportRegistry().register(Nameless())


# -- the Open/Closed claim ---------------------------------------------------------------------------------


def test_a_new_format_needs_no_engine_change() -> None:
    """The whole design goal, in one test."""
    registry = default_registry()
    registry.register(CsvRenderer())

    output = ReportEngine(registry=registry).render(
        ReportEngine().generate([finding()], ReportContext(scan_id="s1")), "csv"
    )

    assert output.startswith("plugin,severity,status")


def test_the_engine_names_no_format_in_its_code() -> None:
    """If the engine hardcoded a format, the registry would be decorative."""
    import ast

    source = Path("src/ragstrike/reporters/engine/report_engine.py")
    tree = ast.parse(source.read_text(encoding="utf-8"))
    docstrings = {
        ast.get_docstring(n, clean=False)
        for n in ast.walk(tree)
        if isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
    }
    literals = [
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value not in docstrings
    ]

    # `default_registry` imports the shipped renderers by name; everything else must not.
    assert not [v for v in literals if v in {"html", "json", "markdown", "pdf"}]


# -- the engine ---------------------------------------------------------------------------------------------


def test_generate_produces_a_model_with_a_scan_id() -> None:
    generated = ReportEngine().generate([finding()], ReportContext(scan_id="s1"))

    assert generated.scan_id == "s1"
    assert generated.report_id


def test_strict_generation_rejects_incoherent_findings() -> None:
    """A report built from incoherent input looks exactly as authoritative as a correct one."""
    with pytest.raises(ReportValidationError):
        ReportEngine().generate([finding(id="")], ReportContext(scan_id="s1"))


def test_non_strict_generation_records_the_problem_instead() -> None:
    generated = ReportEngine().generate([finding(id="")], ReportContext(scan_id="s1"), strict=False)

    assert generated.validation.errors


def test_warnings_travel_with_the_report() -> None:
    """A log line the operator never sees does not tell them anything."""
    generated = ReportEngine().generate([finding(analyzer_version="")], ReportContext(scan_id="s1"))

    assert generated.validation.warnings


def test_render_all_covers_every_available_format() -> None:
    generated = ReportEngine().generate([finding()], ReportContext(scan_id="s1"))

    rendered = ReportEngine().render_all(generated)

    assert set(rendered) == {"html", "json", "markdown", "pdf"}


def test_formats_reports_which_can_actually_render() -> None:
    """PDF is ``True`` when ReportLab is installed and ``False`` when it is not.

    Asserted against the module flag rather than hardcoded, because the answer legitimately differs
    between an install with the ``pdf`` extra and one without -- and a test that hardcoded either
    would fail in a correct environment.
    """
    from ragstrike.reporters.pdf.renderer import REPORTLAB_AVAILABLE

    assert ReportEngine().formats() == {
        "html": True,
        "json": True,
        "markdown": True,
        "pdf": REPORTLAB_AVAILABLE,
    }


def test_context_from_infers_the_scan_id_from_findings() -> None:
    """Repeating it by hand is how the context and the findings drift apart."""
    context = context_from(findings=[finding()])

    assert context.scan_id == "s1"
    assert context.analyzer_version == "1.0.0"


# -- exporter --------------------------------------------------------------------------------------------------


def test_export_writes_a_file(tmp_path: Path) -> None:
    engine = ReportEngine()
    generated = engine.generate([finding()], ReportContext(scan_id="s1"))

    record = ExportManager(engine, tmp_path).export(generated, "markdown")

    assert record.path.is_file()
    assert record.size_bytes > 0


def test_export_creates_a_missing_directory(tmp_path: Path) -> None:
    """A report that fails because nobody made a folder is a bad first experience."""
    engine = ReportEngine()
    generated = engine.generate([finding()], ReportContext(scan_id="s1"))

    record = ExportManager(engine, tmp_path / "deep" / "nested").export(generated, "json")

    assert record.path.is_file()


def test_export_all_writes_every_available_format(tmp_path: Path) -> None:
    """Including PDF, and every file is non-empty and readable back from disk."""
    engine = ReportEngine()
    generated = engine.generate([finding()], ReportContext(scan_id="s1"))

    records = ExportManager(engine, tmp_path).export_all(generated)

    assert {r.fmt for r in records} == set(engine.registry.available())
    assert all(r.path.exists() and r.size_bytes > 0 for r in records)


@pytest.mark.parametrize(
    ("raw", "expected_absent"),
    [("../../etc/passwd", ".."), ("a/b/c.html", "/"), ("x\\y.html", "\\")],
)
def test_filenames_cannot_traverse_directories(raw: str, expected_absent: str) -> None:
    """A scan id reaches this layer from configuration and from a database. A report written to
    ../../etc would be a directory traversal in a security tool."""
    assert expected_absent not in safe_component(raw)


def test_an_unusable_filename_falls_back() -> None:
    """An empty component produces a path nobody intended."""
    assert safe_component("///", fallback="report.html") == "report.html"


def test_exported_content_matches_the_rendered_output(tmp_path: Path) -> None:
    engine = ReportEngine()
    generated = engine.generate([finding()], ReportContext(scan_id="s1"))

    record = ExportManager(engine, tmp_path).export(generated, "json")

    assert json.loads(record.path.read_text(encoding="utf-8"))["cover"]["scan_id"] == "s1"


# -- service ------------------------------------------------------------------------------------------------------


def test_the_service_generates_and_renders_without_a_repository() -> None:
    """Exporting in a CI job with no database is the simplest case; it must not be the hardest."""
    service = ReportService()

    generated = service.generate([finding()], ReportContext(scan_id="s1"))

    assert service.render(generated, "markdown").strip()


def test_persisting_without_a_repository_explains_itself() -> None:
    with pytest.raises(ValueError, match="needs a repository"):
        import asyncio

        asyncio.run(ReportService().list_reports())


def test_the_service_exposes_the_five_documented_operations() -> None:
    """The surface a future Dashboard calls."""
    for operation in ("generate", "list_reports", "load_report", "delete_report", "export"):
        assert hasattr(ReportService(), operation), f"missing {operation}"


# -- configuration ----------------------------------------------------------------------------------------------------


def test_the_shipped_configuration_loads_completely() -> None:
    _, report = load_config(SHIPPED)

    assert report.fully_configured, f"missing={report.missing}"


def test_a_missing_config_directory_degrades_rather_than_aborting(tmp_path: Path) -> None:
    """A tool that refuses to produce a report because one YAML file is absent does not get used --
    but the fallback is reported, never hidden."""
    config, report = load_config(tmp_path)

    assert report.missing
    assert config.title


def test_branding_reaches_the_report() -> None:
    config, _ = load_config(SHIPPED)
    service = ReportService()

    generated = service.generate(
        [finding()], config.context(scan_id="s1", target="http://127.0.0.1:9000")
    )

    assert generated.model.cover.title == config.title


def test_the_context_helper_carries_the_report_version() -> None:
    config, _ = load_config(SHIPPED)

    assert config.context().report_version == config.report_version


def test_build_service_wires_the_configured_truncation_limit(tmp_path: Path) -> None:
    (tmp_path / "reporting.yaml").write_text(
        "reporting:\n  max_detailed_findings: 3\n", encoding="utf-8"
    )

    service, _, _ = build_service(tmp_path)

    assert service.engine.registry.get("markdown").max_detailed_findings == 3


def test_build_service_does_not_require_a_repository() -> None:
    service, config, _ = build_service(SHIPPED)

    assert service.repository is None
    assert config.output_dir


def test_an_absolute_template_directory_is_honoured(tmp_path: Path) -> None:
    (tmp_path / "templates.yaml").write_text(
        f'templates:\n  directory: "{tmp_path.as_posix()}"\n', encoding="utf-8"
    )

    config, _ = load_config(tmp_path)

    assert config.template_dir == tmp_path


def test_a_malformed_config_file_falls_back(tmp_path: Path) -> None:
    (tmp_path / "branding.yaml").write_text("branding: [not, a, mapping\n", encoding="utf-8")

    config, _ = load_config(tmp_path)

    assert config.title  # the default, not a crash
