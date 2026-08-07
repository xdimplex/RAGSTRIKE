"""Tables: the row-shaping functions and one generic renderer.

WHY EVERY LIST GOES THROUGH A `*_rows` FUNCTION
    A Streamlit dataframe will happily render a dataclass by reflection, and then a field rename
    silently changes a column header, a column order, and what an operator is looking at. Naming the
    columns explicitly means the table is a decision someone made rather than a side effect of the
    DTO's field order.

WHY THE VALUES ARE PRE-FORMATTED HERE
    Percentages, durations, and scores are formatted once, in one place, so the same number never
    appears as ``0.94`` in one table and ``94%`` in the next.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ragstrike.dashboard.components.progress import format_duration
from ragstrike.dashboard.services.models import (
    FindingView,
    PluginView,
    ReportView,
    ScanView,
)


def scan_rows(scans: Sequence[ScanView]) -> list[dict[str, Any]]:
    """Scan history rows."""
    return [
        {
            "Scan": scan.id,
            "Target": scan.target,
            "Profile": scan.profile,
            "Result": scan.outcome or scan.state.upper(),
            "Grade": scan.grade or "--",
            "Risk": round(scan.risk_score, 1),
            "Findings": scan.findings_count,
            "Plugins": len(scan.plugins_executed),
            "Duration": format_duration(scan.duration_s) if scan.duration_s else "--",
            "Coverage": f"{scan.coverage * 100:.0f}%" if scan.coverage else "--",
            "Started": scan.started_at,
        }
        for scan in scans
    ]


def findings_rows(findings: Sequence[FindingView]) -> list[dict[str, Any]]:
    """Findings table rows."""
    return [
        {
            "Severity": finding.severity,
            "Status": finding.status,
            "Plugin": finding.plugin,
            "Category": finding.category,
            "Finding": finding.title,
            "Risk": round(finding.risk_score, 1),
            # Confidence is a 0-1 value everywhere in the engine and a percentage everywhere a human
            # reads it. Converting here means no page has to remember which one it is holding.
            "Confidence": f"{finding.confidence * 100:.0f}%",
            "When": finding.timestamp,
        }
        for finding in findings
    ]


def plugin_rows(plugins: Sequence[PluginView]) -> list[dict[str, Any]]:
    """Plugin inventory rows."""
    return [
        {
            "Plugin": plugin.display_name,
            "Slug": plugin.slug,
            "Version": plugin.version,
            "Category": plugin.category,
            "Severity": plugin.severity,
            "Status": "active" if plugin.healthy else "refused",
            "Enabled": plugin.enabled,
            "Requires": ", ".join(plugin.requires),
            "Payloads": plugin.payload_count,
        }
        for plugin in plugins
    ]


def report_rows(reports: Sequence[ReportView]) -> list[dict[str, Any]]:
    """Report listing rows."""
    return [
        {
            "Report": report.id,
            "Scan": report.scan_id,
            "Target": report.target,
            "Format": report.fmt.upper(),
            "Status": report.status or "--",
            "Grade": report.grade or "--",
            "Risk": round(report.risk_score, 1),
            "Findings": report.findings_count,
            "Size": report.size_label,
            "Generated": report.generated_at,
        }
        for report in reports
    ]


#: Columns whose values are identifiers or numbers. Rendered monospace with tabular figures so
#: digits line up down the column and an id can be compared by eye rather than by squinting.
_MONO_COLUMNS = frozenset(
    {"Scan", "Report", "Slug", "Risk", "Findings", "Plugins", "Payloads", "Size", "Version"}
)

#: Columns that carry a status word worth colouring. The value is lowercased and used as a modifier
#: class, so `FAIL` becomes `rs-t-pill--fail` and the palette decides what that looks like.
_PILL_COLUMNS = frozenset({"Result", "Status", "Severity", "Grade", "Enabled"})

#: Right-aligned because they are quantities. A column of numbers aligned left is unreadable.
_NUMERIC_COLUMNS = frozenset(
    {"Risk", "Findings", "Plugins", "Payloads", "Size", "Coverage", "Confidence", "Duration"}
)


def render_table(rows: Sequence[dict[str, Any]], *, height: int = 0) -> None:
    """Draw pre-shaped rows as a FIXED, non-resizable table.

    WHY THIS IS HAND-ROLLED HTML AND NOT ``st.dataframe``
        ``st.dataframe`` renders an interactive grid: every column can be dragged wider or narrower,
        sorted, and the whole thing scrolls independently inside a box that ignores the page's own
        styling. That is a spreadsheet, and it made the console look like one.

        Three concrete problems it caused, all of them reported:

        1. **Columns were resizable.** An operator could drag a report table into an unreadable
           state, and every screenshot of the tool looked different from the last.
        2. **It never took the theme.** The grid is rendered by a component in its own iframe-like
           surface, so switching to dark left the tables pale — the "some part dark, some part
           light" effect.
        3. **It needed pandas** to draw a dozen rows of strings.

        A plain ``<table>`` with ``table-layout: fixed`` solves all three: widths are decided by the
        stylesheet, colours come from the same palette variables as everything else, and there is no
        dependency at all.

    *height* caps the body and makes it scroll internally, for tables that would otherwise run off
    the page. Zero means "as tall as the content".

    Renders nothing at all for an empty sequence: the caller is expected to have already decided
    what its empty state says, and a zero-row table with headers is not that.
    """
    if not rows:
        return

    import streamlit as st

    from ragstrike.dashboard.components.html import escape

    columns = list(rows[0].keys())

    head = "".join(
        f'<th class="{_column_class(name)}" title="{escape(name)}">{escape(name)}</th>'
        for name in columns
    )

    body: list[str] = []
    for row in rows:
        cells: list[str] = []
        for name in columns:
            value = row.get(name, "")
            cells.append(
                f'<td class="{_column_class(name)}" title="{escape(str(value))}">'
                f"{_cell(name, value)}</td>"
            )
        body.append(f"<tr>{''.join(cells)}</tr>")

    # `height` becomes a max-height on the scroll container rather than on the table, so the header
    # stays put (it is sticky) while the rows move under it.
    style = f' style="max-height:{height}px"' if height > 0 else ""
    st.markdown(
        f'<div class="rs-table-wrap"{style}>'
        f'<table class="rs-table"><thead><tr>{head}</tr></thead>'
        f"<tbody>{''.join(body)}</tbody></table></div>",
        unsafe_allow_html=True,
    )


def _column_class(name: str) -> str:
    """The CSS classes for one column, derived from its header."""
    classes = ["rs-t-col"]
    if name in _MONO_COLUMNS:
        classes.append("rs-t-mono")
    if name in _NUMERIC_COLUMNS:
        classes.append("rs-t-num")
    return " ".join(classes)


def _cell(name: str, value: Any) -> str:
    """One cell's inner HTML.

    Status-like columns become coloured pills so severity is readable at a glance down the column;
    everything else is escaped text. The value is always escaped -- a table can contain a target's
    own response, which is to say attacker-influenced text.
    """
    from ragstrike.dashboard.components.html import escape

    if isinstance(value, bool):
        # `True`/`False` reads as debug output. Yes/No is what the column actually means.
        value = "yes" if value else "no"

    text = escape(str(value))
    if name in _PILL_COLUMNS and text and text not in {"--", ""}:
        modifier = _slug(str(value))
        return f'<span class="rs-t-pill rs-t-pill--{modifier}">{text}</span>'
    return text


def _slug(value: str) -> str:
    """A CSS-safe modifier from a cell value: ``"Not run"`` -> ``"not-run"``."""
    return "".join(char if char.isalnum() else "-" for char in value.lower()).strip("-") or "none"
