"""Reports -- list, search, filter, sort, open, export, delete.

RESPONSIBILITY
    The library of generated reports.

WHY "EXPORT" IS A DOWNLOAD AND NOT A FILE WRITE
    The reporting engine writes to the *engine's* filesystem. The dashboard may be running in a
    different container -- the shipped compose file does exactly that -- so a path this page wrote
    would be a path on a machine the operator is not sitting at. Export here means: ask the backend
    to render, hand the bytes to the browser.

PDF
    Listed, disabled, with the reason. It is a declared placeholder in the reporting engine. A
    missing option looks like a bug; a disabled one that says why is information.
"""

from __future__ import annotations

from ragstrike.dashboard.components.cards import report_card
from ragstrike.dashboard.components.controls import confirmation_dialog, facet_options, filter_panel
from ragstrike.dashboard.components.feedback import empty_state, render_exception
from ragstrike.dashboard.components.html import escape, tag
from ragstrike.dashboard.context import PageContext
from ragstrike.dashboard.layouts.page_layout import html, page_header, section
from ragstrike.dashboard.services.errors import DashboardError
from ragstrike.dashboard.services.filters import FilterState, apply_filters, sort_items
from ragstrike.dashboard.services.models import ReportView
from ragstrike.dashboard.services.report_service import MEDIA_TYPES
from ragstrike.dashboard.state.persistence import durable_check, durable_select, durable_text
from ragstrike.dashboard.widgets.tables import render_table, report_rows

PAGE_ID = "reports"
SORT_CHOICES = ("date", "risk", "target", "name")


def render(context: PageContext) -> None:
    page_header("Reports", "Generated assessments, searchable and exportable.")

    if not context.backend_online and not context.demo:
        html(empty_state("▤", "No backend", "Reports are stored and rendered by the API."))
        return

    try:
        reports = context.services.reports.list_reports()
    except DashboardError as exc:
        html(render_exception(context.palette, exc))
        return

    if not reports:
        html(
            empty_state(
                "▤",
                "No reports yet",
                "Reports are generated from a completed scan.",
                hint="Open Scan History and use 'Generate report' on any finished scan.",
            )
        )
        return

    ordered = _toolbar(context, reports)
    if not ordered:
        html(empty_state("▤", "No reports match", "Clear the filters to see them all."))
        return

    # Same order as Scan History: filter -> details -> the full list LAST. The most recent report's
    # detail is what an operator came for; the back catalogue is reference material and belongs
    # under it rather than pushing it below the fold.
    _detail(context, ordered)

    section(f"Report history ({len(ordered)})")
    render_table(report_rows(ordered))


def _toolbar(context: PageContext, reports: list[ReportView]) -> list[ReportView]:
    import streamlit as st

    # See scan_history: plain widgets lose their value the moment the section is left.
    columns = st.columns([3, 1, 1])
    with columns[0]:
        query = durable_text(
            "Search reports",
            "rs.rep.search",
            placeholder="Search by scan name, report id, target, or format...",
            label_visibility="collapsed",
        )
    with columns[1]:
        sort_key = durable_select("Sort by", SORT_CHOICES, "rs.rep.sort")
    with columns[2]:
        descending = durable_check("Descending", "rs.rep.desc", default=True)

    stored = context.state.filters_for(PAGE_ID)
    previous = stored.get("state")
    base = previous if isinstance(previous, FilterState) else FilterState()

    with st.expander("Filters", expanded=False):
        updated = filter_panel(
            base.with_text(str(query or "")),
            facet_options(reports),
            key="rs.rep.filters",
            facets=("status", "target", "date", "risk"),
        )
    stored["state"] = updated

    return sort_items(apply_filters(reports, updated), str(sort_key), descending=bool(descending))


def _detail(context: PageContext, reports: list[ReportView]) -> None:
    import streamlit as st

    section("Detail")

    # READABLE LABELS AS THE OPTIONS, and uniqueness ENFORCED rather than assumed -- the same two
    # rules Scan History arrived at the hard way.
    #
    # Not `format_func`: with a `key`, Streamlit resolves the replayed selection through the
    # FORMATTED label, so a stored raw id stops matching and a different report is selected. Not a
    # bare name either: one scan commonly has several reports (HTML and PDF, plus regenerated
    # copies), so labels collide, later entries overwrite earlier ones in the map, and the page
    # opens a report the operator did not choose. The generation timestamp settles ties.
    by_label: dict[str, ReportView] = {}
    for item in reports:
        label = item.label
        if label in by_label:
            label = f"{label}  ·  {item.generated_at or item.id}"
        by_label[label] = item

    labels = list(by_label)
    remembered = context.state.selected_report
    index = next((i for i, name in enumerate(labels) if by_label[name].id == remembered), 0)
    chosen_label = st.selectbox("Report", labels, index=index, key="rs.rep.selected")
    report = by_label[str(chosen_label)]
    context.state.selected_report = report.id

    # Card and actions in one bordered container: as siblings, the card's border rendered across
    # "Open report" and "Delete". Same defect and same fix as the Plugins and Scan History pages.
    with st.container(border=True):
        html(report_card(context.palette, report, framed=False))

        actions = st.columns(3)
        with actions[0]:
            _open(context, report)
        with actions[1]:
            _export(context, report)
        with actions[2]:
            if confirmation_dialog(
                key=f"rs.rep.delete.{report.id}",
                action="Delete",
                subject=report.label,
                state=context.state,
            ):
                _delete(context, report)


def _open(context: PageContext, report: ReportView) -> None:
    import streamlit as st

    # ONE control, not two.
    #
    # There were two: a link that opened the report in a tab, and a "Preview here" button that
    # rendered it into a 720px sandboxed frame below. The frame was the older of the two and the
    # worse one -- a report is the deliverable of this whole tool, and viewing it through a
    # letterbox reads as unfinished. Two buttons doing almost the same thing is also a choice the
    # reader has to make for no benefit.
    #
    # The link points at the API, not the dashboard. A report is rendered from target responses --
    # attacker-influenced text -- so it must never be spliced into the dashboard's own origin. The
    # API is a separate origin holding no cookie or session for a script in a report to reach.
    # ALWAYS HTML, whatever format this report was generated in.
    #
    # HTML is the only format a browser reliably renders as a document in a tab: a PDF depends on
    # the viewer's plugin, and Markdown and JSON display as source. The label is fixed for the same
    # reason -- a button whose text changed with the row told the reader about the stored file
    # rather than about what pressing it does.
    #
    # The API renders the HTML on demand if the scan has none on disk, so this link cannot 404 on a
    # report that was only ever generated as PDF.
    inline_url = context.services.reports.inline_url(report.scan_id, "html")
    if not inline_url:
        st.caption("Preview needs the HTTP backend.")
        return
    html(
        tag(
            "a",
            escape("Preview in HTML"),
            href=inline_url,
            target="_blank",
            rel="noopener noreferrer",
            class_="rs-openlink",
        )
    )


def _export(context: PageContext, report: ReportView) -> None:
    import streamlit as st

    formats = context.services.reports.formats()
    choices = list(formats) or list(MEDIA_TYPES)
    chosen = st.selectbox(
        "Export as",
        choices,
        index=choices.index(report.fmt) if report.fmt in choices else 0,
        key=f"rs.rep.fmt.{report.id}",
        format_func=lambda name: name.upper()
        + ("" if formats.get(name, True) else "  (not available)"),
    )
    available = formats.get(str(chosen), True)
    if not available:
        st.caption("This format is declared but not implemented yet.")

    if not st.button(
        "Prepare export",
        key=f"rs.rep.export.{report.id}",
        width="stretch",
        disabled=not available,
    ):
        return

    try:
        generated = context.services.reports.generate(report.scan_id, str(chosen))
        rendered = context.services.reports.open_report(report.scan_id, generated.id, generated.fmt)
    except DashboardError as exc:
        html(render_exception(context.palette, exc))
        return

    # `.data` rather than `.content`: a PDF arrives base64-encoded, and handing that string to the
    # download button would produce a file full of base64 text with a .pdf extension.
    st.download_button(
        f"Download {rendered.filename}",
        data=rendered.data,
        file_name=rendered.filename,
        mime=rendered.media_type,
        key=f"rs.rep.dl.{report.id}",
        width="stretch",
    )


def _delete(context: PageContext, report: ReportView) -> None:
    import streamlit as st

    try:
        context.services.reports.delete_report(report.id)
    except DashboardError as exc:
        html(render_exception(context.palette, exc))
        return
    context.state.selected_report = ""
    context.notify("warning", f"Report deleted: {report.label}.")
    st.rerun()
