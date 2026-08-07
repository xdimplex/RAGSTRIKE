"""Markdown renderer -- the format that survives being pasted into a ticket.

Chosen defaults worth stating: no HTML fallbacks, no reference-style links, no tables wider than
they need to be. Markdown is read as often in a terminal or a diff as in a rendered view, and a
renderer that only looks right in one of those is only half useful.

**Charts render as data, not pictures.** A Markdown report lists the chart's values in a table.
Nothing here draws.
"""

from __future__ import annotations

from ragstrike.reporters.base.renderer import BaseRenderer
from ragstrike.reporters.models.formatting import format_duration
from ragstrike.reporters.models.report import FindingEntry, ReportModel

_SEVERITY_MARK = {
    "CRITICAL": "🔴",
    "HIGH": "🟠",
    "MEDIUM": "🟡",
    "LOW": "🔵",
    "INFO": "⚪",
}

_STATUS_MARK = {
    "FAIL": "❌",
    "PASS": "✅",
    "INCONCLUSIVE": "❔",
    "ERROR": "⚠️",
    "SKIPPED": "⏭️",
}


class MarkdownRenderer(BaseRenderer):
    """Renders a report as GitHub-flavoured Markdown."""

    name = "markdown"
    extension = "md"
    media_type = "text/markdown"

    #: Findings beyond this are summarized rather than detailed. A scan with two hundred findings
    #: produces a document nobody scrolls; the count is always stated so the truncation is visible.
    max_detailed_findings = 50

    def render(self, report: ReportModel) -> str:
        parts = [
            self._cover(report),
            self._summary(report),
            self._risk(report),
            self._categories(report),
            self._findings(report),
            self._recommendations(report),
            self._statistics(report),
            self._timeline(report),
            self._charts(report),
        ]
        return "\n\n".join(part for part in parts if part).strip() + "\n"

    # -- sections --------------------------------------------------------------------------------

    def _cover(self, report: ReportModel) -> str:
        cover = report.cover

        # Built as (label, value) pairs rather than by inserting into a list of rendered lines.
        #
        # The previous version did `lines.insert(5, ...)` to add the Organization row, and index 5
        # is the `|---|---|` separator -- so setting an organization pushed the separator DOWN and
        # produced a table with a data row above its own header rule, which every markdown renderer
        # displays as broken. Index arithmetic over formatted output is exactly the kind of thing
        # that works until someone adds a line above it.
        rows: list[tuple[str, str]] = []
        if cover.organization:
            rows.append(("Organization", cover.organization))
        rows += [
            ("Target", f"`{cover.target or 'unknown'}`"),
            ("Scan ID", f"`{cover.scan_id or 'unknown'}`"),
            ("Generated", cover.generated_at.isoformat()),
            ("Framework", cover.framework_version or "unknown"),
            ("Analyzer", cover.analyzer_version or "unknown"),
        ]

        return "\n".join(
            [
                f"# {cover.title}",
                "",
                f"**{cover.project}** · report v{cover.report_version}",
                "",
                "| | |",
                "|---|---|",
                *(f"| {label} | {value} |" for label, value in rows),
            ]
        )

    def _summary(self, report: ReportModel) -> str:
        s = report.summary
        return "\n".join(
            [
                "## Executive Summary",
                "",
                f"**{s.status}** — {s.headline}",
                "",
                "| Metric | Value |",
                "|---|---|",
                f"| Overall risk score | **{s.risk_score:.2f}** / 10 |",
                f"| Confidence | {s.confidence:.0%} ({s.confidence_band}) |",
                f"| Coverage | {s.coverage:.0%} |",
                f"| Plugins executed | {s.plugins_executed} |",
                f"| Passed | {s.passed} |",
                f"| Failed | {s.failed} |",
                f"| Inconclusive | {s.inconclusive} |",
                f"| Errored | {s.errored} |",
                f"| Skipped | {s.skipped} |",
                f"| Duration | {format_duration(s.duration_ms)} |",
            ]
        )

    def _risk(self, report: ReportModel) -> str:
        r = report.risk
        rows = [
            f"| {_SEVERITY_MARK['CRITICAL']} Critical | {r.critical} |",
            f"| {_SEVERITY_MARK['HIGH']} High | {r.high} |",
            f"| {_SEVERITY_MARK['MEDIUM']} Medium | {r.medium} |",
            f"| {_SEVERITY_MARK['LOW']} Low | {r.low} |",
            f"| {_SEVERITY_MARK['INFO']} Informational | {r.informational} |",
        ]
        return "\n".join(
            [
                "## Risk Breakdown",
                "",
                "| Severity | Findings |",
                "|---|---|",
                *rows,
                "",
                f"**{r.actionable}** actionable finding{'s' if r.actionable != 1 else ''}.",
            ]
        )

    def _categories(self, report: ReportModel) -> str:
        if not report.categories:
            return ""
        rows = [
            f"| {c.label} | {c.score:.2f} | {c.findings} | {c.passed} | {c.failed} | "
            f"{c.confidence:.0%} |"
            for c in report.categories
        ]
        return "\n".join(
            [
                "## Category Summary",
                "",
                "| Category | Score | Findings | Pass | Fail | Confidence |",
                "|---|---|---|---|---|---|",
                *rows,
            ]
        )

    def _findings(self, report: ReportModel) -> str:
        if not report.findings:
            return "## Detailed Findings\n\nNo findings recorded."

        shown = report.findings[: self.max_detailed_findings]
        omitted = len(report.findings) - len(shown)

        blocks = ["## Detailed Findings", ""]
        for finding in shown:
            blocks.append(self._finding(finding))
        if omitted:
            blocks.append(
                f"_{omitted} further finding{'s' if omitted != 1 else ''} omitted from the "
                f"detailed section. The JSON export contains all {len(report.findings)}._"
            )
        return "\n\n".join(blocks)

    def _finding(self, f: FindingEntry) -> str:
        mark = _STATUS_MARK.get(f.status, "")
        severity = _SEVERITY_MARK.get(f.severity, "")
        lines = [
            f"### {mark} {f.plugin} — {f.severity} {severity}",
            "",
            f"`{f.finding_id}`",
            "",
            "| | |",
            "|---|---|",
            f"| Status | **{f.status}** |",
            f"| Category | {f.category or 'uncategorized'} |",
            f"| Severity | {f.severity} |",
            f"| Confidence | {f.confidence:.0%} ({f.confidence_band}) |",
            f"| Risk score | {f.risk_score:.2f} |",
            f"| Execution time | {format_duration(f.execution_ms)} |",
        ]

        if f.description:
            lines += ["", f"**Observed.** {f.description}"]
        if f.notes:
            lines += ["", f"**Analysis.** {f.notes}"]

        if not f.evidence.is_empty:
            lines += ["", "**Evidence.**", ""]
            if f.evidence.sources:
                lines.append(f"- Sources: {', '.join(f'`{s}`' for s in f.evidence.sources)}")
            if f.evidence.chunk_ids:
                lines.append(f"- Chunks: {', '.join(f'`{c}`' for c in f.evidence.chunk_ids)}")
            for signal in f.evidence.signals[:5]:
                detector = signal.get("detector", "signal")
                detail = signal.get("detail", "")
                lines.append(f"- `{detector}`: {detail}")
            if f.evidence.text:
                lines += ["", "```text", f.evidence.text[:500], "```"]

        if f.recommendation:
            lines += ["", f"**Recommendation.** {f.recommendation}"]
            if f.remediation:
                lines += ["", f.remediation]
        if f.references:
            lines += ["", "**References.**", ""]
            lines += [f"- <{ref}>" for ref in f.references]

        return "\n".join(lines)

    def _recommendations(self, report: ReportModel) -> str:
        if not report.recommendations:
            return ""
        blocks = ["## Recommendations", ""]
        for group in report.recommendations:
            mark = _SEVERITY_MARK.get(group.severity, "")
            blocks.append(f"### {mark} {group.severity}")
            for item in group.items:
                count = len(item.get("findings", []))
                blocks.append(
                    f"- **{item['title']}** "
                    f"({count} finding{'s' if count != 1 else ''}"
                    + (f", effort {item['effort']}" if item.get("effort") else "")
                    + ")"
                )
                if item.get("remediation"):
                    blocks.append(f"  {item['remediation']}")
        return "\n".join(blocks)

    def _statistics(self, report: ReportModel) -> str:
        s = report.statistics
        return "\n".join(
            [
                "## Scan Statistics",
                "",
                "| Metric | Value |",
                "|---|---|",
                f"| Duration | {format_duration(s.duration_ms)} |",
                f"| Plugins | {s.plugin_count} |",
                f"| Findings | {s.finding_count} |",
                f"| Average per plugin | {format_duration(int(s.average_plugin_ms))} |",
                f"| Slowest plugin | {s.slowest_plugin or 'n/a'} "
                f"({format_duration(s.slowest_plugin_ms)}) |",
                f"| Analyzer version | {s.analyzer_version or 'unknown'} |",
                f"| Framework version | {s.framework_version or 'unknown'} |",
                f"| Scoring model | {s.scoring_model_version or 'unknown'} |",
            ]
        )

    def _timeline(self, report: ReportModel) -> str:
        if not report.timeline:
            return ""
        rows = [f"| {e.at.isoformat()} | {e.label} | {e.detail or ''} |" for e in report.timeline]
        return "\n".join(["## Timeline", "", "| Time | Event | Detail |", "|---|---|---|", *rows])

    def _charts(self, report: ReportModel) -> str:
        """Chart **data**, as tables. Nothing here draws."""
        if not report.charts:
            return ""
        blocks = ["## Chart Data", "", "_Data models for rendering elsewhere; no images._", ""]
        for chart in report.charts:
            if not chart.labels:
                continue
            blocks.append(f"### {chart.title}")
            blocks.append("")
            blocks.append("| Label | Value |")
            blocks.append("|---|---|")
            values = chart.values or (0.0,) * len(chart.labels)
            for label, value in zip(chart.labels, values, strict=False):
                blocks.append(f"| {label} | {value:g} |")
            blocks.append("")
        return "\n".join(blocks)


__all__ = ["MarkdownRenderer"]
