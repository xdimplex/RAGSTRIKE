"""Renderer and validator tests.

The renderer property that matters most is not layout — it is that **every value is escaped**. A
report contains model output, retrieved document text, and prompt fragments, all attacker-influenced
by construction. A security tool whose report executes what it found would be the most embarrassing
possible vulnerability, and it is exactly the shape of bug this codebase exists to detect.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json

import pytest

from ragstrike.analyzers.base.finding import Finding
from ragstrike.models.values.enums import PluginOutcome, Severity
from ragstrike.reporters.builders.report_builder import ReportBuilder, ReportContext
from ragstrike.reporters.html.renderer import HtmlRenderer
from ragstrike.reporters.json.renderer import JsonRenderer
from ragstrike.reporters.markdown.renderer import MarkdownRenderer
from ragstrike.reporters.models.formatting import format_duration
from ragstrike.reporters.models.report import ReportModel
from ragstrike.reporters.pdf.renderer import PdfRenderer, RendererNotImplementedError
from ragstrike.reporters.templates.template_manager import TemplateManager
from ragstrike.reporters.validators.report_validator import (
    ReportValidationError,
    ReportValidator,
)

NOW = datetime(2026, 7, 30, 12, 0, 0, tzinfo=UTC)

RENDERERS = [HtmlRenderer(), JsonRenderer(), MarkdownRenderer()]


def finding(**kwargs) -> Finding:
    defaults = {
        "id": "f1",
        "scan_id": "s1",
        "plugin_id": "prompt-injection",
        "category": "prompt_injection",
        "status": PluginOutcome.FAIL,
        "severity": Severity.HIGH,
        "confidence": 0.9,
        "confidence_band": "high",
        "risk_score": 7.2,
        "timestamp": NOW,
        "analyzer_version": "1.0.0",
        "recommendation": "Separate instructions from data",
        "references": ("https://owasp.org/llm01",),
        "notes": "injection-confirmed fired",
        "evidence": {
            "summary": "1/4 payloads returned FAIL",
            "text": "the model replied",
            "sources": ["handbook.pdf"],
            "chunk_ids": ["c0"],
            "signals": [{"detector": "canary", "detail": "canary present"}],
            "timing": {"execution_ms": 120},
        },
        "metadata": {
            "execution_ms": 120,
            "remediation": "Use role separation.",
            "effort": "MEDIUM",
        },
    }
    defaults.update(kwargs)
    return Finding(**defaults)


def model(findings: list[Finding] | None = None, **context) -> ReportModel:
    context.setdefault("scan_id", "s1")
    context.setdefault("target", "http://127.0.0.1:9000")
    context.setdefault("generated_at", NOW)
    return ReportBuilder().build(
        findings if findings is not None else [finding()], ReportContext(**context)
    )


# -- every renderer ---------------------------------------------------------------------------------


@pytest.mark.parametrize("renderer", RENDERERS, ids=lambda r: r.name)
def test_every_renderer_produces_output(renderer) -> None:
    assert renderer.render(model()).strip()


@pytest.mark.parametrize("renderer", RENDERERS, ids=lambda r: r.name)
def test_rendering_is_deterministic(renderer) -> None:
    """Same model in, same bytes out. A renderer that varied would make two exports of one scan
    disagree."""
    built = model()

    assert renderer.render(built) == renderer.render(built)


@pytest.mark.parametrize("renderer", RENDERERS, ids=lambda r: r.name)
def test_every_renderer_handles_an_empty_report(renderer) -> None:
    """A scan that found nothing still deserves a report saying so."""
    assert renderer.render(model([])).strip()


@pytest.mark.parametrize("renderer", RENDERERS, ids=lambda r: r.name)
def test_every_renderer_declares_an_extension_and_media_type(renderer) -> None:
    assert renderer.extension and renderer.media_type


@pytest.mark.parametrize("renderer", RENDERERS, ids=lambda r: r.name)
def test_filenames_use_the_scan_id(renderer) -> None:
    """The scan id is what an operator recognises in a directory listing."""
    name = renderer.filename(model())

    assert "s1" in name
    assert name.endswith(renderer.extension)


@pytest.mark.parametrize("renderer", RENDERERS, ids=lambda r: r.name)
def test_every_renderer_shows_the_headline_status(renderer) -> None:
    assert "VULNERABLE" in renderer.render(model())


# -- HTML escaping ------------------------------------------------------------------------------------


def test_html_escapes_script_tags_from_evidence() -> None:
    """The load-bearing security property of this renderer."""
    hostile = finding(evidence={"text": "<script>alert('xss')</script>", "summary": ""})

    html = HtmlRenderer().render(model([hostile]))

    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


def test_html_escapes_the_target_and_title() -> None:
    html = HtmlRenderer().render(model(target="<img src=x onerror=alert(1)>"))

    assert "<img src=x" not in html


def test_html_escapes_a_hostile_plugin_name() -> None:
    html = HtmlRenderer().render(model([finding(plugin_id="<b>evil</b>")]))

    assert "<b>evil</b>" not in html


def test_html_escapes_detector_details() -> None:
    hostile = finding(evidence={"signals": [{"detector": "<x>", "detail": "<script>bad</script>"}]})

    html = HtmlRenderer().render(model([hostile]))

    assert "<script>bad" not in html


def test_html_escapes_quotes_in_references() -> None:
    """Quotes matter: an unescaped one breaks out of the href attribute."""
    html = HtmlRenderer().render(model([finding(references=('" onmouseover="alert(1)',))]))

    assert 'onmouseover="alert(1)"' not in html


def test_html_is_self_contained() -> None:
    """A report is emailed and opened from a downloads folder. One that depends on sibling files
    or fetches remote assets is broken in both situations."""
    html = HtmlRenderer().render(model())

    assert "<style>" in html
    assert "http://" not in html.split("<style>")[0]
    assert 'src="http' not in html


def test_html_has_one_document_structure() -> None:
    html = HtmlRenderer().render(model())

    assert html.count("<!DOCTYPE html>") == 1
    assert html.count("</html>") == 1


# -- JSON ---------------------------------------------------------------------------------------------


def test_json_round_trips() -> None:
    payload = json.loads(JsonRenderer().render(model()))

    assert payload["cover"]["scan_id"] == "s1"
    assert payload["findings"][0]["plugin"] == "prompt-injection"


def test_json_contains_every_section() -> None:
    payload = json.loads(JsonRenderer().render(model()))

    for section in (
        "cover",
        "executive_summary",
        "risk_breakdown",
        "category_summary",
        "findings",
        "recommendations",
        "statistics",
        "timeline",
        "charts",
    ):
        assert section in payload, f"missing {section}"


def test_json_preserves_report_order_rather_than_sorting() -> None:
    """Sections are ordered as a human reads them; a machine consumer does not care, so sorting
    would scramble the readable order for no gain."""
    keys = list(json.loads(JsonRenderer().render(model())))

    assert keys.index("cover") < keys.index("findings")


def test_json_carries_all_findings_even_when_markdown_truncates() -> None:
    findings = [finding(id=f"f{i}") for i in range(60)]

    payload = json.loads(JsonRenderer().render(model(findings)))

    assert len(payload["findings"]) == 60


# -- Markdown --------------------------------------------------------------------------------------------


def test_markdown_has_the_expected_headings() -> None:
    text = MarkdownRenderer().render(model())

    for heading in ("# ", "## Executive Summary", "## Risk Breakdown", "## Detailed Findings"):
        assert heading in text


def test_markdown_truncates_long_reports_and_says_so() -> None:
    """A document nobody scrolls is not a report. The omission is always stated."""
    renderer = MarkdownRenderer()
    renderer.max_detailed_findings = 5

    text = renderer.render(model([finding(id=f"f{i}") for i in range(20)]))

    assert "15 further findings omitted" in text
    assert "JSON export contains all 20" in text


def test_markdown_renders_charts_as_tables_not_images() -> None:
    text = MarkdownRenderer().render(model())

    assert "## Chart Data" in text
    assert "![" not in text


def test_markdown_reports_no_findings_explicitly() -> None:
    assert "No findings recorded." in MarkdownRenderer().render(model([]))


# -- PDF placeholder ----------------------------------------------------------------------------------------


def test_the_pdf_renderer_produces_a_real_pdf() -> None:
    """No longer a placeholder.

    The rule it enforced still holds and is asserted here: **never emit a file that claims to be a
    PDF and is not.** The difference is that the answer is now usually "yes". Full coverage of the
    document itself lives in ``test_pdf_renderer.py``.
    """
    if not PdfRenderer().implemented:
        pytest.skip("the pdf extra is not installed in this environment")

    payload = PdfRenderer().render_bytes(model())

    assert payload.startswith(b"%PDF-")


def test_the_pdf_renderer_declares_itself_available_when_the_library_is() -> None:
    """``implemented`` is computed from the import, not hardcoded either way."""
    from ragstrike.reporters.pdf.renderer import REPORTLAB_AVAILABLE

    assert PdfRenderer().implemented is REPORTLAB_AVAILABLE


def test_the_pdf_refusal_names_the_install_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """The honest-degradation path when the extra is absent."""
    import ragstrike.reporters.pdf.renderer as renderer_module

    monkeypatch.setattr(renderer_module, "REPORTLAB_AVAILABLE", False)

    with pytest.raises(RendererNotImplementedError) as excinfo:
        PdfRenderer().render_bytes(model())

    assert "pip install" in excinfo.value.hint
    assert "html" in excinfo.value.hint


# -- templates ------------------------------------------------------------------------------------------------


def test_templates_substitute_named_placeholders() -> None:
    assert TemplateManager.apply("Hello $name", name="world") == "Hello world"


def test_a_stray_dollar_does_not_lose_the_report() -> None:
    """An operator's customized template with a literal $ should render, not raise."""
    assert "$5" in TemplateManager.apply("costs $5 and $name", name="x")


def test_templates_never_evaluate_expressions() -> None:
    """str.Template understands $name and nothing else. A templating language that could execute
    would turn styling a report into a code-execution surface."""
    rendered = TemplateManager.apply("${__import__('os').system('x')}", name="x")

    assert "__import__" in rendered  # left as a literal, not run


def test_the_default_templates_are_complete() -> None:
    """A report renders with no customization at all."""
    templates = TemplateManager().load()

    assert "$body" in templates.html
    assert templates.css.strip()


def test_a_missing_template_directory_falls_back(tmp_path) -> None:
    templates = TemplateManager(tmp_path / "nope").load()

    assert "$body" in templates.html


def test_a_custom_template_is_used(tmp_path) -> None:
    (tmp_path / "report.html").write_text("CUSTOM $body", encoding="utf-8")

    html = HtmlRenderer(templates=TemplateManager(tmp_path)).render(model())

    assert html.startswith("CUSTOM")


# -- formatting --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ms", "expected"), [(350, "350ms"), (1500, "1.5s"), (65000, "1m 5s"), (0, "0ms")]
)
def test_duration_formatting(ms: int, expected: str) -> None:
    assert format_duration(ms) == expected


def test_both_renderers_format_durations_identically() -> None:
    """They had private copies of this before; that is how two formats start disagreeing about the
    same scan."""
    built = model()

    assert format_duration(120) in HtmlRenderer().render(built)
    assert format_duration(120) in MarkdownRenderer().render(built)


# -- validation ------------------------------------------------------------------------------------------------------


def test_valid_findings_pass() -> None:
    assert ReportValidator().validate_findings([finding()]).valid


def test_a_finding_with_no_id_is_rejected() -> None:
    """A finding that cannot be referenced, cited, or looked up later stops the build."""
    report = ReportValidator().validate_findings([finding(id="")])

    assert not report.valid


def test_findings_from_two_scans_are_rejected() -> None:
    """A report covers exactly one scan; mixing them would produce a document that is true of
    neither."""
    report = ReportValidator().validate_findings([finding(), finding(scan_id="s2")])

    assert not report.valid
    assert any(e.field == "scan_id" for e in report.errors)


def test_no_findings_is_a_warning_not_an_error() -> None:
    """A scan that genuinely found nothing still deserves a report saying so."""
    report = ReportValidator().validate_findings([])

    assert report.valid
    assert report.warnings


def test_an_out_of_range_confidence_warns() -> None:
    report = ReportValidator().validate_findings([finding(confidence=5.0)])

    assert report.valid
    assert any(w.field == "confidence" for w in report.warnings)


def test_a_missing_analyzer_version_warns() -> None:
    """A finding that cannot be traced to the rules that produced it is weaker evidence."""
    report = ReportValidator().validate_findings([finding(analyzer_version="")])

    assert any(w.field == "analyzer_version" for w in report.warnings)


def test_raise_if_invalid_names_what_failed() -> None:
    report = ReportValidator().validate_findings([finding(id="")])

    with pytest.raises(ReportValidationError) as excinfo:
        report.raise_if_invalid()

    assert excinfo.value.hint


def test_a_built_model_validates() -> None:
    assert ReportValidator().validate_model(model()).valid


def test_model_validation_catches_a_count_mismatch() -> None:
    """Catches builder bugs: if the risk breakdown disagrees with the findings list, one of them is
    wrong and a reader cannot tell which."""
    import dataclasses

    built = model()
    broken = dataclasses.replace(built, risk=dataclasses.replace(built.risk, critical=99))

    assert not ReportValidator().validate_model(broken).valid
