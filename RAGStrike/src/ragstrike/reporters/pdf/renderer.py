"""PDF renderer.

WHY REPORTLAB AND NOT WEASYPRINT
    WeasyPrint was the declared optional dependency for fifteen phases and never once produced a
    file, because it binds to GTK/Pango/Cairo -- native libraries absent from a stock Windows
    machine and unobtainable through ``pip``. A "PDF extra" that fails at import on the platform the
    project is developed on is not an extra.

    ReportLab is pure Python. It installs from PyPI everywhere, needs no system packages, and is the
    library the Phase 16 dependency list names.

WHY IT STILL DEGRADES HONESTLY
    ``implemented`` is **computed** from whether ReportLab actually imported, not hardcoded. With the
    ``pdf`` extra installed the format renders; without it, ``formats()`` reports ``pdf: false`` and
    asking for it raises a message naming the install command.

    That preserves the rule the placeholder existed to enforce -- **never emit a file that claims to
    be a PDF and is not** -- with the difference that the honest answer is now usually "yes".

WHAT THE DOCUMENT CONTAINS
    The same sections every other format carries, because they come from one model. A renderer
    presents; it never calculates. If this file computed a total, HTML and PDF could disagree about
    the same scan, and the disagreement would reach a user before it reached a test.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

from ragstrike.core.errors import RAGStrikeError
from ragstrike.reporters.base.renderer import BaseRenderer
from ragstrike.reporters.models.formatting import format_duration
from ragstrike.reporters.models.report import ReportModel

try:  # pragma: no cover - depends on whether the extra is installed
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    REPORTLAB_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on the environment
    REPORTLAB_AVAILABLE = False


class RendererNotImplementedError(RAGStrikeError):
    """A declared format that cannot render in this installation.

    Descends from ``RAGStrikeError`` so the CLI's existing exit-code mapping handles it like every
    other deliberate failure.
    """

    code = "renderer_not_implemented"


#: Severity -> swatch. Deliberately small: colour never carries meaning on its own here, because a
#: report printed in monochrome must stay readable. The severity word is always beside the colour.
_SEVERITY_COLOUR = {
    "CRITICAL": "#7f1d1d",
    "HIGH": "#b45309",
    "MEDIUM": "#a16207",
    "LOW": "#1d4ed8",
    "INFO": "#374151",
}

#: Beyond this, findings are summarised rather than detailed -- the same cut-off the Markdown
#: renderer uses, so the two formats truncate at the same point. The count is always stated.
_MAX_DETAILED_FINDINGS = 50


class PdfRenderer(BaseRenderer):
    """Renders a report as PDF via ReportLab."""

    name = "pdf"
    extension = "pdf"
    media_type = "application/pdf"
    binary = True

    #: Computed, not asserted. The format is available exactly when the library is.
    implemented = REPORTLAB_AVAILABLE

    def render(self, report: ReportModel) -> str:
        """The text path, which a PDF does not have.

        Returns a short note rather than raising, so a caller that reached the text path by mistake
        gets something intelligible instead of a stack trace. Anything writing a file goes through
        :meth:`render_bytes`, which the exporter selects on ``binary``.
        """
        self._require_reportlab()
        return (
            f"PDF report {report.report_id} for scan {report.scan_id or 'unknown'}. "
            "Binary output; use render_bytes()."
        )

    def render_bytes(self, report: ReportModel) -> bytes:
        """The real renderer."""
        self._require_reportlab()

        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            title=report.cover.title or "RAGStrike report",
            author=report.cover.organization or "RAGStrike",
            subject=f"Security evaluation of {report.cover.target or 'a RAG system'}",
        )

        styles = _styles()
        story: list[Any] = []
        story += self._cover(report, styles)
        story += self._summary(report, styles)
        story += self._risk(report, styles)
        story += self._categories(report, styles)
        story += self._findings(report, styles)
        story += self._recommendations(report, styles)
        story += self._statistics(report, styles)
        story += self._methodology(styles)

        document.build(story)
        return buffer.getvalue()

    # -- sections --------------------------------------------------------------------------------

    def _cover(self, report: ReportModel, styles: dict[str, Any]) -> list[Any]:
        cover = report.cover
        return [
            Paragraph(_esc(cover.title or "RAGStrike security report"), styles["title"]),
            Spacer(1, 6 * mm),
            _kv_table(
                [
                    ("Target", cover.target or "-"),
                    ("Scan", cover.scan_id or "-"),
                    ("Generated", cover.generated_at.strftime("%Y-%m-%d %H:%M UTC")),
                    ("Framework", cover.framework_version or "-"),
                    ("Analyzer", cover.analyzer_version or "-"),
                    ("Organization", cover.organization or "-"),
                ]
            ),
            Spacer(1, 8 * mm),
        ]

    def _summary(self, report: ReportModel, styles: dict[str, Any]) -> list[Any]:
        summary = report.summary
        return [
            Paragraph("Executive summary", styles["h1"]),
            Paragraph(_esc(summary.headline), styles["body"]),
            Spacer(1, 3 * mm),
            _kv_table(
                [
                    ("Status", summary.status),
                    ("Risk score", f"{summary.risk_score:.2f} / 10"),
                    # Coverage sits beside the verdict, always. A result from 40% coverage and one
                    # from 100% are different claims (ADR-020).
                    ("Coverage", f"{summary.coverage * 100:.0f}%"),
                    ("Confidence", f"{summary.confidence:.2f} ({summary.confidence_band})"),
                    ("Plugins executed", str(summary.plugins_executed)),
                    (
                        "Outcomes",
                        f"{summary.passed} passed · {summary.failed} failed · "
                        f"{summary.inconclusive} inconclusive · {summary.errored} errored · "
                        f"{summary.skipped} skipped",
                    ),
                    ("Duration", format_duration(summary.duration_ms)),
                ]
            ),
            Spacer(1, 6 * mm),
        ]

    def _risk(self, report: ReportModel, styles: dict[str, Any]) -> list[Any]:
        risk = report.risk
        rows: list[tuple[str, ...]] = [("Severity", "Findings")]
        rows += [
            ("Critical", str(risk.critical)),
            ("High", str(risk.high)),
            ("Medium", str(risk.medium)),
            ("Low", str(risk.low)),
            ("Informational", str(risk.informational)),
        ]
        return [
            Paragraph("Risk breakdown", styles["h1"]),
            _grid(rows),
            Spacer(1, 3 * mm),
            Paragraph(
                f"{risk.actionable} actionable of {risk.total} total. "
                "Counts are failures only -- a PASS graded INFO is the absence of a finding.",
                styles["body"],
            ),
            Spacer(1, 6 * mm),
        ]

    def _categories(self, report: ReportModel, styles: dict[str, Any]) -> list[Any]:
        if not report.categories:
            return []
        rows: list[tuple[str, ...]] = [
            ("Category", "Findings", "Passed", "Failed", "Score", "Worst")
        ]
        rows += [
            (
                category.label or category.category,
                str(category.findings),
                str(category.passed),
                str(category.failed),
                f"{category.score:.2f}",
                category.worst_severity,
            )
            for category in report.categories
        ]
        return [Paragraph("Categories", styles["h1"]), _grid(rows), Spacer(1, 6 * mm)]

    def _findings(self, report: ReportModel, styles: dict[str, Any]) -> list[Any]:
        story: list[Any] = [PageBreak(), Paragraph("Findings", styles["h1"])]
        if not report.findings:
            story.append(Paragraph("No findings were recorded for this scan.", styles["body"]))
            return story

        shown = report.findings[:_MAX_DETAILED_FINDINGS]
        for finding in shown:
            colour = _SEVERITY_COLOUR.get(finding.severity, "#374151")
            story.append(
                Paragraph(
                    f'<font color="{colour}"><b>{_esc(finding.severity)}</b></font> '
                    f"&nbsp;{_esc(finding.status)} &nbsp;&middot;&nbsp; {_esc(finding.plugin)}",
                    styles["h2"],
                )
            )
            story.append(
                _kv_table(
                    [
                        ("Finding", finding.finding_id),
                        ("Category", finding.category),
                        ("Risk", f"{finding.risk_score:.2f}"),
                        ("Confidence", f"{finding.confidence:.2f} ({finding.confidence_band})"),
                    ]
                )
            )
            if finding.description:
                story.append(Paragraph(_esc(finding.description), styles["body"]))
            if finding.recommendation:
                story.append(
                    Paragraph(
                        f"<b>Recommendation.</b> {_esc(finding.recommendation)}", styles["body"]
                    )
                )
            story.append(Spacer(1, 4 * mm))

        if len(report.findings) > len(shown):
            # Stated, never silent. A truncated list that does not say so reads as a complete one.
            story.append(
                Paragraph(
                    f"{len(report.findings) - len(shown)} further finding(s) omitted from the "
                    f"detailed section. The JSON export carries all {len(report.findings)}.",
                    styles["body"],
                )
            )
        return story

    def _recommendations(self, report: ReportModel, styles: dict[str, Any]) -> list[Any]:
        if not report.recommendations:
            return []
        story: list[Any] = [PageBreak(), Paragraph("Recommendations", styles["h1"])]
        for group in report.recommendations:
            story.append(Paragraph(f"{_esc(group.severity)} ({group.count})", styles["h2"]))
            for item in group.items:
                title = str(item.get("title") or item.get("recommendation") or "")
                detail = str(item.get("detail") or item.get("remediation") or "")
                story.append(Paragraph(f"&bull; <b>{_esc(title)}</b>", styles["body"]))
                if detail:
                    story.append(Paragraph(_esc(detail), styles["body"]))
            story.append(Spacer(1, 3 * mm))
        return story

    def _statistics(self, report: ReportModel, styles: dict[str, Any]) -> list[Any]:
        stats = report.statistics
        return [
            Paragraph("Statistics", styles["h1"]),
            _kv_table(
                [
                    ("Duration", format_duration(stats.duration_ms)),
                    ("Plugins", str(stats.plugin_count)),
                    ("Findings", str(stats.finding_count)),
                    ("Average plugin", f"{stats.average_plugin_ms:.0f} ms"),
                    (
                        "Slowest plugin",
                        f"{stats.slowest_plugin or '-'} ({stats.slowest_plugin_ms} ms)",
                    ),
                    ("Framework", stats.framework_version or "-"),
                    ("Analyzer", stats.analyzer_version or "-"),
                    ("Scoring model", stats.scoring_model_version or "-"),
                ]
            ),
            Spacer(1, 6 * mm),
        ]

    def _methodology(self, styles: dict[str, Any]) -> list[Any]:
        return [
            Paragraph("Methodology and limitations", styles["h1"]),
            Paragraph(
                "RAGStrike tests a defined set of RAG-specific weakness classes with a defined set "
                "of payloads. <b>Absence of findings is not proof of security.</b> Read the "
                "coverage figure beside the verdict: a scan that could only run part of its "
                "intended cases is a different statement from one that ran them all.",
                styles["body"],
            ),
        ]

    # -- internals -------------------------------------------------------------------------------

    @staticmethod
    def _require_reportlab() -> None:
        if not REPORTLAB_AVAILABLE:
            raise RendererNotImplementedError(
                "PDF rendering needs ReportLab, which is not installed.",
                hint=(
                    'Install it with `pip install "ragstrike[pdf]"`, or use html, markdown, or '
                    "json -- all three are always available."
                ),
            )


def _styles() -> dict[str, Any]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "RSTitle", parent=base["Title"], fontSize=20, spaceAfter=4, alignment=TA_LEFT
        ),
        "h1": ParagraphStyle("RSH1", parent=base["Heading1"], fontSize=14, spaceBefore=8),
        "h2": ParagraphStyle("RSH2", parent=base["Heading2"], fontSize=11, spaceBefore=6),
        "body": ParagraphStyle("RSBody", parent=base["BodyText"], fontSize=9, leading=13),
    }


def _kv_table(rows: list[tuple[str, str]]) -> Table:
    table = Table([[key, Paragraph(_esc(value), _cell())] for key, value in rows])
    table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#4b5563")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _grid(rows: list[tuple[str, ...]]) -> Table:
    table = Table([[_esc(str(cell)) for cell in row] for row in rows])
    table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _cell() -> Any:
    return ParagraphStyle("RSCell", fontName="Helvetica", fontSize=9, leading=12)


def _esc(value: str) -> str:
    """Escape for ReportLab's mini-markup.

    A report carries model output and retrieved document text -- both attacker-influenced by
    construction, since getting text into the corpus *is* the attack. An unescaped ``<`` would let a
    payload close a tag and reshape or corrupt the document. Same reasoning as the HTML renderer's
    escaping, against the same input, for the same reason.
    """
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


__all__ = ["REPORTLAB_AVAILABLE", "PdfRenderer", "RendererNotImplementedError"]
