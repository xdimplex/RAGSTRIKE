"""PDF renderer tests.

PDF was a declared placeholder that refused for fifteen phases. The declared dependency was
WeasyPrint, which binds to GTK/Pango/Cairo and cannot install on a stock Windows machine -- so the
"pdf extra" never worked anywhere the project was developed. Phase 16 replaced it with ReportLab,
which is pure Python.

These tests check the three things that matter: the bytes are a real PDF, the document actually
contains the report, and attacker-influenced text cannot reshape it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ragstrike.reporters.config import build_service, load_config
from ragstrike.reporters.exporters.export_manager import ExportManager
from ragstrike.reporters.models.report import (
    CoverPage,
    ExecutiveSummary,
    FindingEntry,
    ReportModel,
    RiskBreakdown,
)
from ragstrike.reporters.pdf.renderer import (
    REPORTLAB_AVAILABLE,
    PdfRenderer,
    RendererNotImplementedError,
)

pytestmark = pytest.mark.skipif(
    not REPORTLAB_AVAILABLE, reason="the pdf extra is not installed in this environment"
)


def _model(*findings: FindingEntry) -> ReportModel:
    return ReportModel(
        report_id="rpt-1",
        cover=CoverPage(
            title="Test report",
            scan_id="scan-1",
            target="lab",
            generated_at=datetime(2026, 7, 31, 12, 0, tzinfo=UTC),
        ),
        summary=ExecutiveSummary(
            status="FAIL",
            risk_score=7.4,
            coverage=0.42,
            headline="Three weaknesses were demonstrated.",
            plugins_executed=5,
            failed=3,
        ),
        risk=RiskBreakdown(critical=1, high=2),
        findings=findings,
    )


def _finding(**overrides: object) -> FindingEntry:
    defaults = {
        "finding_id": "f001",
        "plugin": "prompt-injection",
        "category": "prompt_injection",
        "severity": "HIGH",
        "status": "FAIL",
        "confidence": 0.9,
        "risk_score": 7.2,
        "description": "A payload in a retrieved document changed the answer.",
        "recommendation": "Delimit retrieved context and declare it as data.",
    }
    defaults.update(overrides)
    return FindingEntry(**defaults)  # type: ignore[arg-type]


# ------------------------------------------------------------------------------------------------
# It produces a real PDF
# ------------------------------------------------------------------------------------------------


def test_render_bytes_produces_a_real_pdf() -> None:
    """Magic bytes, not a plausible-looking file with the right extension."""
    payload = PdfRenderer().render_bytes(_model(_finding()))

    assert payload.startswith(b"%PDF-")
    assert payload.rstrip().endswith(b"%%EOF")
    assert len(payload) > 1_000


def test_the_document_is_readable_and_contains_the_report() -> None:
    pypdf = pytest.importorskip("pypdf")
    payload = PdfRenderer().render_bytes(_model(_finding()))

    import io

    reader = pypdf.PdfReader(io.BytesIO(payload))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert reader.pages
    for section in (
        "Executive summary",
        "Risk breakdown",
        "Findings",
        "Statistics",
        "Methodology",
    ):
        assert section in text, section


def test_coverage_is_printed_beside_the_verdict() -> None:
    """ADR-020. A result from 42% coverage must not render like one from 100%."""
    pypdf = pytest.importorskip("pypdf")
    import io

    payload = PdfRenderer().render_bytes(_model(_finding()))
    reader = pypdf.PdfReader(io.BytesIO(payload))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert "Coverage" in text
    assert "42%" in text


def test_the_format_is_reported_as_available() -> None:
    """The engine's ``formats()`` is what a caller checks before asking."""
    service, _, _ = build_service()

    assert service.engine.formats()["pdf"] is True
    assert service.engine.is_binary("pdf") is True
    assert service.engine.is_binary("html") is False


# ------------------------------------------------------------------------------------------------
# Attacker-influenced text cannot reshape the document
# ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "hostile",
    [
        "<b>bold</b> injected markup",
        '<font color="red">recoloured</font>',
        "unbalanced <para tag",
        "ampersand & angle < bracket >",
    ],
)
def test_hostile_finding_text_does_not_break_rendering(hostile: str) -> None:
    """A report carries model output and retrieved document text.

    Both are attacker-influenced by construction -- getting text into the corpus *is* the attack. An
    unescaped ``<`` would let a payload close a ReportLab tag and reshape or corrupt the document.
    """
    payload = PdfRenderer().render_bytes(_model(_finding(description=hostile)))

    assert payload.startswith(b"%PDF-")


def test_hostile_markup_is_rendered_as_text_not_as_markup() -> None:
    """The escaping must be *exercised*, not merely present.

    Asserting that a tag is absent from a document that never contained the text would pass against
    a renderer that dropped the field entirely -- a test that cannot fail.
    """
    pypdf = pytest.importorskip("pypdf")
    import io

    marker = "ZZQX"
    payload = PdfRenderer().render_bytes(
        _model(_finding(description=f"<b>{marker}</b> and <i>tags</i>"))
    )
    reader = pypdf.PdfReader(io.BytesIO(payload))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    # The text reached the document...
    assert marker in text
    # ...and the tags around it were rendered literally rather than interpreted.
    assert f"<b>{marker}</b>" in text


# ------------------------------------------------------------------------------------------------
# Export
# ------------------------------------------------------------------------------------------------


def test_export_writes_bytes_not_encoded_text(tmp_path: Path) -> None:
    """Round-tripping a PDF through UTF-8 corrupts it silently.

    The result is a file with the right name and extension that no reader can open -- exactly the
    failure the placeholder era was designed to prevent, arriving by a different route.
    """
    config, _ = load_config()
    service, _, _ = build_service()
    generated = service.generate([], config.context(scan_id="scan-export"))

    record = ExportManager(service.engine, tmp_path).export(generated, "pdf")

    assert record.path.exists()
    assert record.path.read_bytes().startswith(b"%PDF-")
    assert record.size_bytes == record.path.stat().st_size


def test_export_all_now_includes_pdf(tmp_path: Path) -> None:
    """``export_all`` skips unavailable formats. PDF is no longer one of them."""
    config, _ = load_config()
    service, _, _ = build_service()
    generated = service.generate([], config.context(scan_id="scan-all"))

    records = ExportManager(service.engine, tmp_path).export_all(generated)

    assert {r.fmt for r in records} == {"html", "json", "markdown", "pdf"}
    assert all(r.path.exists() and r.size_bytes > 0 for r in records)


def test_the_text_path_returns_a_note_rather_than_raising() -> None:
    """A caller that reached ``render`` by mistake should get something intelligible."""
    note = PdfRenderer().render(_model())

    assert "render_bytes" in note
    assert not note.startswith("%PDF")


def test_a_missing_library_would_refuse_with_an_install_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The honest-degradation path, still intact.

    Never emit a file that claims to be a PDF and is not -- that rule outlived the placeholder.
    """
    import ragstrike.reporters.pdf.renderer as module

    monkeypatch.setattr(module, "REPORTLAB_AVAILABLE", False)

    with pytest.raises(RendererNotImplementedError) as caught:
        PdfRenderer().render_bytes(_model())

    assert "ReportLab" in str(caught.value)
    assert "pip install" in caught.value.hint
