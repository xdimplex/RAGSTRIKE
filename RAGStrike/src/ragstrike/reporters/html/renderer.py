"""HTML renderer -- the format a person reads.

**Every value is escaped.** A report contains model output, retrieved document text, and prompt
fragments -- all of it attacker-influenced by construction. This is a security tool; a report that
executes what it found would be the most embarrassing possible vulnerability, and it is exactly the
shape of bug this codebase exists to detect.

Nothing is fetched at render time either. Styles are inlined, and the only image reference is
whatever an operator configured as a logo. A report that phones home when opened is a tracking
pixel, whatever it was intended to be.
"""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

from ragstrike.reporters.base.renderer import BaseRenderer
from ragstrike.reporters.models.formatting import format_duration
from ragstrike.reporters.models.report import FindingEntry, ReportModel
from ragstrike.reporters.templates.template_manager import (
    AssetManager,
    TemplateManager,
    TemplateSet,
)

#: Values longer than this are words, not figures, and step down a type size so they fit their card.
#: Eight covers every status the analyzer emits except VULNERABLE and INCONCLUSIVE, which are the
#: two that overflowed.
_LONG_VALUE_CHARS = 8


def _size_class(value: object) -> str:
    return " long" if len(str(value)) > _LONG_VALUE_CHARS else ""


class HtmlRenderer(BaseRenderer):
    """Renders a self-contained HTML document."""

    name = "html"
    extension = "html"
    media_type = "text/html"

    def __init__(
        self,
        templates: TemplateManager | None = None,
        assets: AssetManager | None = None,
    ) -> None:
        self.templates = templates or TemplateManager()
        self.assets = assets or AssetManager()

    def render(self, report: ReportModel) -> str:
        template: TemplateSet = self.templates.load()
        body = "\n".join(
            section
            for section in (
                self._cover(report),
                self._summary(report),
                self._risk(report),
                self._categories(report),
                self._findings(report),
                self._recommendations(report),
                self._statistics(report),
                self._timeline(report),
                self._charts(report),
            )
            if section
        )
        return TemplateManager.apply(
            template.html,
            title=esc(report.cover.title),
            css=template.css,
            body=body,
            footer=esc(template.footer),
        )

    # -- sections --------------------------------------------------------------------------------

    def _cover(self, report: ReportModel) -> str:
        cover = report.cover
        logo = self.assets.logo(cover.logo)
        logo_html = f'<p class="muted">{esc(logo)}</p>' if logo else ""
        rows = [
            ("Target", cover.target or "unknown"),
            ("Scan ID", cover.scan_id or "unknown"),
            ("Generated", cover.generated_at.isoformat()),
            ("Framework", cover.framework_version or "unknown"),
            ("Analyzer", cover.analyzer_version or "unknown"),
            ("Report version", cover.report_version),
        ]
        if cover.organization:
            rows.insert(0, ("Organization", cover.organization))

        return (
            f"<h1>{esc(cover.title)}</h1>"
            f'<p class="muted">{esc(cover.project)}</p>'
            f"{logo_html}"
            + _table(("", ""), [(esc(k), f"<code>{esc(v)}</code>") for k, v in rows], head=False)
        )

    def _summary(self, report: ReportModel) -> str:
        s = report.summary
        cards = [
            ("Status", esc(s.status)),
            ("Risk score", f"{s.risk_score:.2f}"),
            ("Confidence", f"{s.confidence:.0%}"),
            ("Coverage", f"{s.coverage:.0%}"),
            ("Failed", str(s.failed)),
            ("Inconclusive", str(s.inconclusive)),
        ]
        # `long` on values that are words rather than figures -- "VULNERABLE" at the numeric type
        # size is what overflowed the card in the first place.
        card_html = "".join(
            f'<div class="card"><div class="label">{label}</div>'
            f'<div class="value{_size_class(value)}">{value}</div></div>'
            for label, value in cards
        )
        return (
            "<h2>Executive Summary</h2>"
            f'<div class="headline">{esc(s.headline)}</div>'
            f'<div class="summary">{card_html}</div>'
            + _table(
                ("Metric", "Value"),
                [
                    ("Plugins executed", str(s.plugins_executed)),
                    ("Passed", str(s.passed)),
                    ("Failed", str(s.failed)),
                    ("Inconclusive", str(s.inconclusive)),
                    ("Errored", str(s.errored)),
                    ("Skipped", str(s.skipped)),
                    ("Duration", format_duration(s.duration_ms)),
                ],
            )
        )

    def _risk(self, report: ReportModel) -> str:
        r = report.risk
        rows = [
            (_badge("CRITICAL"), str(r.critical)),
            (_badge("HIGH"), str(r.high)),
            (_badge("MEDIUM"), str(r.medium)),
            (_badge("LOW"), str(r.low)),
            (_badge("INFO"), str(r.informational)),
        ]
        return (
            "<h2>Risk Breakdown</h2>"
            + _table(("Severity", "Findings"), rows)
            + f'<p class="muted">{r.actionable} actionable finding'
            f"{'s' if r.actionable != 1 else ''}.</p>"
        )

    def _categories(self, report: ReportModel) -> str:
        if not report.categories:
            return ""
        rows = [
            (
                esc(c.label),
                f"{c.score:.2f}",
                str(c.findings),
                str(c.passed),
                str(c.failed),
                f"{c.confidence:.0%}",
            )
            for c in report.categories
        ]
        return "<h2>Category Summary</h2>" + _table(
            ("Category", "Score", "Findings", "Pass", "Fail", "Confidence"), rows
        )

    def _findings(self, report: ReportModel) -> str:
        if not report.findings:
            return "<h2>Detailed Findings</h2><p>No findings recorded.</p>"
        return "<h2>Detailed Findings</h2>" + "".join(self._finding(f) for f in report.findings)

    def _finding(self, f: FindingEntry) -> str:
        parts = [
            '<div class="finding">',
            f"<h3>{esc(f.plugin)} {_badge(f.severity)} "
            f'<span class="st-{esc(f.status)}">{esc(f.status)}</span></h3>',
            f'<p class="muted"><code>{esc(f.finding_id)}</code></p>',
            _table(
                ("", ""),
                [
                    ("Category", esc(f.category or "uncategorized")),
                    ("Confidence", f"{f.confidence:.0%} ({esc(f.confidence_band)})"),
                    ("Risk score", f"{f.risk_score:.2f}"),
                    ("Execution time", format_duration(f.execution_ms)),
                ],
                head=False,
            ),
        ]

        if f.description:
            parts.append(f"<p><strong>Observed.</strong> {esc(f.description)}</p>")
        if f.notes:
            parts.append(f"<p><strong>Analysis.</strong> {esc(f.notes)}</p>")

        if not f.evidence.is_empty:
            parts.append("<p><strong>Evidence.</strong></p><ul>")
            if f.evidence.sources:
                joined = ", ".join(f"<code>{esc(s)}</code>" for s in f.evidence.sources)
                parts.append(f"<li>Sources: {joined}</li>")
            if f.evidence.chunk_ids:
                joined = ", ".join(f"<code>{esc(c)}</code>" for c in f.evidence.chunk_ids)
                parts.append(f"<li>Chunks: {joined}</li>")
            for signal in f.evidence.signals[:5]:
                detector = esc(str(signal.get("detector", "signal")))
                detail = esc(str(signal.get("detail", "")))
                parts.append(f"<li><code>{detector}</code>: {detail}</li>")
            parts.append("</ul>")
            if f.evidence.text:
                parts.append(f"<pre>{esc(f.evidence.text[:1000])}</pre>")

        if f.recommendation:
            parts.append(f"<p><strong>Recommendation.</strong> {esc(f.recommendation)}</p>")
            if f.remediation:
                parts.append(f"<p>{esc(f.remediation)}</p>")
        if f.references:
            links = "".join(
                f'<li><a href="{esc(r)}" rel="noopener noreferrer">{esc(r)}</a></li>'
                for r in f.references
            )
            parts.append(f"<p><strong>References.</strong></p><ul>{links}</ul>")

        parts.append("</div>")
        return "".join(parts)

    def _recommendations(self, report: ReportModel) -> str:
        if not report.recommendations:
            return ""
        parts = ["<h2>Recommendations</h2>"]
        for group in report.recommendations:
            parts.append(f"<h3>{_badge(group.severity)}</h3><ul>")
            for item in group.items:
                count = len(item.get("findings", []))
                effort = f", effort {esc(str(item['effort']))}" if item.get("effort") else ""
                parts.append(
                    f"<li><strong>{esc(str(item['title']))}</strong> "
                    f'<span class="muted">({count} finding'
                    f"{'s' if count != 1 else ''}{effort})</span>"
                )
                if item.get("remediation"):
                    parts.append(f"<br>{esc(str(item['remediation']))}")
                parts.append("</li>")
            parts.append("</ul>")
        return "".join(parts)

    def _statistics(self, report: ReportModel) -> str:
        s = report.statistics
        return "<h2>Scan Statistics</h2>" + _table(
            ("Metric", "Value"),
            [
                ("Duration", format_duration(s.duration_ms)),
                ("Plugins", str(s.plugin_count)),
                ("Findings", str(s.finding_count)),
                ("Average per plugin", format_duration(int(s.average_plugin_ms))),
                (
                    "Slowest plugin",
                    f"{esc(s.slowest_plugin or 'n/a')} ({format_duration(s.slowest_plugin_ms)})",
                ),
                ("Analyzer version", esc(s.analyzer_version or "unknown")),
                ("Framework version", esc(s.framework_version or "unknown")),
                ("Scoring model", esc(s.scoring_model_version or "unknown")),
            ],
        )

    def _timeline(self, report: ReportModel) -> str:
        if not report.timeline:
            return ""
        rows = [
            (f"<code>{esc(e.at.isoformat())}</code>", esc(e.label), esc(e.detail))
            for e in report.timeline
        ]
        return "<h2>Timeline</h2>" + _table(("Time", "Event", "Detail"), rows)

    def _charts(self, report: ReportModel) -> str:
        """Chart **data** as tables. This renderer draws nothing -- see ChartDataBuilder."""
        if not report.charts:
            return ""
        parts = [
            "<h2>Chart Data</h2>",
            '<p class="muted">Data models for rendering elsewhere; no images are generated.</p>',
        ]
        for chart in report.charts:
            if not chart.labels:
                continue
            values = chart.values or (0.0,) * len(chart.labels)
            rows = [
                (esc(label), f"{value:g}")
                for label, value in zip(chart.labels, values, strict=False)
            ]
            parts.append(f"<h3>{esc(chart.title)}</h3>")
            parts.append(_table(("Label", "Value"), rows))
        return "".join(parts)


# -- helpers ---------------------------------------------------------------------------------------


def esc(value: object) -> str:
    """Escape for HTML, quotes included.

    Report content is attacker-influenced by construction -- model output, retrieved documents,
    prompt fragments. Everything interpolated goes through here.
    """
    return escape(str(value), quote=True)


def _badge(severity: str) -> str:
    return f'<span class="badge sev-{esc(severity)}">{esc(severity)}</span>'


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]], *, head: bool = True) -> str:
    """Build a table. Cells are inserted verbatim, so callers escape before calling.

    ``Sequence`` rather than ``list``/``tuple``: ``list`` is invariant, so a caller passing
    ``list[tuple[str, str]]`` would not satisfy ``list[tuple[str, ...]]`` even though every row is
    a perfectly good row.
    """
    parts = ["<table>"]
    if head and any(headers):
        parts.append("<thead><tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr></thead>")
    parts.append("<tbody>")
    for row in rows:
        parts.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
    parts.append("</tbody></table>")
    return "".join(parts)


__all__ = ["HtmlRenderer"]
