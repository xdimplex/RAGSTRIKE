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
from ragstrike.dashboard.context import PageContext
from ragstrike.dashboard.layouts.page_layout import html, page_header, section
from ragstrike.dashboard.services.errors import DashboardError
from ragstrike.dashboard.services.filters import FilterState, apply_filters, sort_items
from ragstrike.dashboard.services.models import ReportView
from ragstrike.dashboard.services.report_service import MEDIA_TYPES
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

    section(f"Reports ({len(ordered)})")
    render_table(report_rows(ordered))
    _detail(context, ordered)


def _toolbar(context: PageContext, reports: list[ReportView]) -> list[ReportView]:
    import streamlit as st

    columns = st.columns([3, 1, 1])
    with columns[0]:
        query = st.text_input(
            "Search reports",
            key="rs.rep.search",
            placeholder="Search by report id, scan id, target, or format...",
            label_visibility="collapsed",
        )
    with columns[1]:
        sort_key = st.selectbox("Sort by", SORT_CHOICES, key="rs.rep.sort")
    with columns[2]:
        descending = st.checkbox("Descending", value=True, key="rs.rep.desc")

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
    ids = [report.id for report in reports]
    remembered = context.state.selected_report
    index = ids.index(remembered) if remembered in ids else 0
    chosen_id = st.selectbox("Report", ids, index=index, key="rs.rep.selected")
    context.state.selected_report = str(chosen_id)
    report = next(r for r in reports if r.id == chosen_id)

    html(report_card(context.palette, report))

    actions = st.columns(3)
    with actions[0]:
        _open(context, report)
    with actions[1]:
        _export(context, report)
    with actions[2]:
        if confirmation_dialog(
            key=f"rs.rep.delete.{report.id}",
            action="Delete",
            subject=report.id,
            state=context.state,
        ):
            _delete(context, report)


def _open(context: PageContext, report: ReportView) -> None:
    import streamlit as st

    if not st.button("Open report", key=f"rs.rep.open.{report.id}", width="stretch"):
        return
    try:
        rendered = context.services.reports.open_report(report.scan_id, report.id, report.fmt)
    except DashboardError as exc:
        html(render_exception(context.palette, exc))
        return

    if rendered.is_binary:
        # A PDF has no inline representation here, so offer the file instead of pasting base64 into
        # the page. Streamlit cannot embed a PDF viewer without shipping the bytes to the browser
        # anyway, and a download is the honest affordance.
        st.download_button(
            f"Download {rendered.filename}",
            data=rendered.data,
            file_name=rendered.filename,
            mime=rendered.media_type,
            key=f"rs.rep.opendl.{report.id}",
            width="stretch",
        )
    elif report.fmt == "html":
        # Rendered inside a sandboxed component rather than injected into the page. A report is
        # built from target responses, which is to say from text an attacker influenced; splicing it
        # into the dashboard's own DOM would make the report an XSS vector against the tool that
        # produced it.
        st.components.v1.html(rendered.content, height=720, scrolling=True)
    elif report.fmt == "markdown":
        st.markdown(rendered.content)
    else:
        st.code(rendered.content, language=report.fmt)


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
    context.notify("warning", f"Report {report.id} deleted.")
    st.rerun()
