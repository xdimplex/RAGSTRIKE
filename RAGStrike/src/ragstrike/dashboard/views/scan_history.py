"""Scan History -- every previous scan, with detail, comparison, replay, and report generation.

RESPONSIBILITY
    The record. Everything here is read-only except the two buttons that ask the backend to do
    something new with an old scan: generate a report, or replay it.

COMPARISON IS A BACKEND CALL
    Diffing two scans looks like set arithmetic on finding titles and is not: finding identity is
    the analyzer's rule, and comparing across scoring-model versions is refused rather than
    approximated (ADR-011). Computing it here would produce a second, subtly wrong answer that
    renders in exactly the same table as the right one.
"""

from __future__ import annotations

from ragstrike.dashboard.components.badges import grade_hero
from ragstrike.dashboard.components.cards import metric_card, summary_card
from ragstrike.dashboard.components.controls import facet_options, filter_panel
from ragstrike.dashboard.components.feedback import empty_state, render_exception
from ragstrike.dashboard.components.progress import format_duration, severity_bars
from ragstrike.dashboard.context import PageContext
from ragstrike.dashboard.layouts.page_layout import columns_of, html, page_header, rail, section
from ragstrike.dashboard.services.errors import DashboardError
from ragstrike.dashboard.services.filters import FilterState, apply_filters, sort_items
from ragstrike.dashboard.services.models import ScanView
from ragstrike.dashboard.widgets.tables import findings_rows, render_table, scan_rows

PAGE_ID = "scan_history"

#: Comparison needs two finished scans to have anything to compare.
MIN_COMPARABLE_SCANS = 2


def render(context: PageContext) -> None:
    page_header("Scan History", "Every scan RAGStrike has run, and how they compare.")

    if not context.backend_online and not context.demo:
        html(empty_state("◷", "No backend", "Scan history is stored by the API."))
        return

    try:
        scans = context.services.history.list_scans()
    except DashboardError as exc:
        html(render_exception(context.palette, exc))
        return

    if not scans:
        html(empty_state("◷", "No scans yet", "Launch one from Scan Center."))
        return

    ordered = _toolbar(context, scans)
    if not ordered:
        html(empty_state("◷", "No scans match", "Clear the filters to see them all."))
        return

    # The status rail: the facts an operator wants visible without opening a row. Computed from the
    # scans already loaded, so it costs nothing and can never disagree with the table beneath it.
    finished = [s for s in ordered if s.finished]
    failing = [s for s in finished if s.outcome == "FAIL"]
    rail(
        [
            ("Scans", str(len(ordered))),
            ("Targets", str(len({s.target for s in ordered if s.target}))),
            ("With findings", str(len(failing))),
            ("Worst risk", f"{max((s.risk_score for s in finished), default=0.0):.1f}"),
            (
                "Best coverage",
                f"{max((s.coverage for s in finished), default=0.0) * 100:.0f}%",
            ),
        ]
    )

    # ORDER: filter -> details -> findings -> compare -> the full table LAST.
    #
    # The table used to come first, so the most recent scan's details -- the thing an operator opened
    # this page to read -- sat below twenty rows of history and, on a normal window, below the fold.
    # History is reference material: useful, and rarely the reason anyone arrived. It reads better as
    # an appendix than as a preamble.
    #
    # `_detail` renders the selected scan's summary, its actions and its findings, in that order.
    _detail(context, ordered)
    _compare(context, scans)

    section(f"Scan history ({len(ordered)})")
    render_table(scan_rows(ordered))


def _toolbar(context: PageContext, scans: list[ScanView]) -> list[ScanView]:
    import streamlit as st

    columns = st.columns([3, 1, 1])
    with columns[0]:
        query = st.text_input(
            "Search scans",
            key="rs.hist.search",
            placeholder="Search by scan id, name, target, or profile...",
            label_visibility="collapsed",
        )
    with columns[1]:
        sort_key = st.selectbox("Sort by", ("date", "risk", "target", "name"), key="rs.hist.sort")
    with columns[2]:
        descending = st.checkbox("Descending", value=True, key="rs.hist.desc")

    stored = context.state.filters_for(PAGE_ID)
    previous = stored.get("state")
    base = previous if isinstance(previous, FilterState) else FilterState()

    with st.expander("Filters", expanded=False):
        updated = filter_panel(
            base.with_text(str(query or "")),
            facet_options(scans),
            key="rs.hist.filters",
            facets=("status", "target", "date", "risk"),
        )
    stored["state"] = updated

    return sort_items(apply_filters(scans, updated), str(sort_key), descending=bool(descending))


def _detail(context: PageContext, scans: list[ScanView]) -> None:
    import streamlit as st

    section("Detail")
    # Readable labels as the OPTIONS, not via `format_func`.
    #
    # `format_func` was the obvious way to keep ids as values and show names, and it silently broke
    # selection: with a `key`, the replayed choice is resolved through the FORMATTED label, so the
    # stored id stopped matching and a different scan was selected. That is not cosmetic -- "Replay
    # scan" would then have replayed a scan the operator never picked.
    #
    # Labels carry the id suffix so two scans of the same target and profile stay distinguishable,
    # and the map back to the id is explicit.
    # Uniqueness is ENFORCED, not assumed.
    #
    # The first attempt suffixed `scan.id[:8]`, which is unique for a 32-character hex id and not
    # for the short ids the demo transport uses -- "scan-0006"[:8] is "scan-000", identical for
    # every scan in the list. Labels collided, later scans overwrote earlier ones in the map, and
    # picking the first entry returned a scan the operator had not chosen. "Replay scan" would then
    # have replayed the wrong one, which is a good deal worse than an ugly dropdown.
    by_label: dict[str, ScanView] = {}
    for scan_item in scans:
        parts = [
            scan_item.name or "unnamed",
            scan_item.target or "no target",
            scan_item.profile or "no profile",
        ]
        label = "  ·  ".join(parts)
        if label in by_label:
            label = f"{label}  ·  {scan_item.id}"
        by_label[label] = scan_item

    chosen_label = st.selectbox("Scan", list(by_label), key="rs.hist.selected")
    scan = by_label[str(chosen_label)]

    # The summary and its actions in ONE bordered container.
    #
    # They were siblings: an HTML summary card, then a bare `st.columns` row of buttons. Nothing tied
    # them together, so the card rendered across "Replay scan" and "Open in Reports" -- the buttons
    # belonged to the scan visually and to the page structurally, and the layout followed the
    # structure. Inside a container they are one flex column and the gap is spacing, not a collision.
    with st.container(border=True):
        left, middle, right = st.columns([1, 2, 2])
        with left:
            html(grade_hero(context.palette, scan.grade, coverage=scan.coverage or 1.0))
        with middle:
            html(
                summary_card(
                    scan.name or scan.id,
                    {
                        "Target": scan.target,
                        "Profile": scan.profile or "--",
                        "Result": scan.outcome or scan.state.upper(),
                        "Risk": f"{scan.risk_score:.1f} / 100",
                        "Duration": format_duration(scan.duration_s),
                        "Plugins executed": str(scan.plugins_ran),
                        "Started": scan.started_at,
                        # The full id, once, where it is needed for correlating with a report --
                        # rather than as the row label in a table of twenty.
                        "Scan id": scan.id,
                    },
                    framed=False,
                )
            )
        with right:
            html(severity_bars(context.palette, scan.severity_counts) or "")

        if scan.plugins_executed:
            st.caption("Plugins executed: " + ", ".join(scan.plugins_executed))

        _actions(context, scan)

    _findings(context, scan)


def _actions(context: PageContext, scan: ScanView) -> None:
    import streamlit as st

    actions = st.columns(3)
    with actions[0]:
        _generate_report(context, scan)
    if actions[1].button("Replay scan", key=f"rs.hist.replay.{scan.id}"):
        _replay(context, scan)
    if actions[2].button("Open in Reports", key=f"rs.hist.reports.{scan.id}"):
        context.navigate("reports")
        st.rerun()


def _generate_report(context: PageContext, scan: ScanView) -> None:
    import streamlit as st

    formats = context.services.reports.formats()
    choices = [name for name, ready in formats.items() if ready] or ["html"]
    chosen = st.selectbox(
        "Report format",
        choices,
        index=(
            choices.index(context.config.reports.default_format)
            if context.config.reports.default_format in choices
            else 0
        ),
        key=f"rs.hist.fmt.{scan.id}",
    )
    if not st.button("Generate report", key=f"rs.hist.gen.{scan.id}", type="primary"):
        return
    try:
        report = context.services.reports.generate(scan.id, str(chosen))
    except DashboardError as exc:
        html(render_exception(context.palette, exc))
        return
    context.state.selected_report = report.id
    context.notify("success", f"Report {report.id} generated.", f"{scan.id} as {chosen}.")
    st.rerun()


def _replay(context: PageContext, scan: ScanView) -> None:
    """Re-run a previous scan's configuration against the same target.

    A *new* scan with the old plan, not a re-analysis of stored evidence -- the engine's own
    ``replay`` command is the latter, and conflating the two would let an operator think they had
    re-tested when they had only re-scored. The authorization confirmation is required again,
    because it was given for a scan that already finished.
    """
    import streamlit as st

    context.state.current_target = scan.target
    context.state.loaded_plugins = list(scan.plugins_executed)
    context.notify(
        "info",
        "Replay prepared in Scan Center.",
        "Confirm authorization there to start it — a previous confirmation does not carry over.",
    )
    context.navigate("scan_center")
    st.rerun()


def _findings(context: PageContext, scan: ScanView) -> None:
    section("Findings")
    try:
        findings = context.services.scans.findings(scan.id)
    except DashboardError as exc:
        html(render_exception(context.palette, exc))
        return
    if not findings:
        html(empty_state("✓", "No findings recorded for this scan"))
        return
    render_table(findings_rows(findings))


def _compare(context: PageContext, scans: list[ScanView]) -> None:
    import streamlit as st

    finished = [scan for scan in scans if scan.finished]
    if len(finished) < MIN_COMPARABLE_SCANS:
        return

    section("Compare")
    ids = [scan.id for scan in finished]
    left, right = st.columns(2)
    base_id = left.selectbox("Base", ids, index=min(1, len(ids) - 1), key="rs.hist.base")
    head_id = right.selectbox("Head", ids, index=0, key="rs.hist.head")

    if base_id == head_id:
        st.caption("Pick two different scans.")
        return
    if not st.button("Compare", key="rs.hist.compare", type="primary"):
        return

    try:
        comparison = context.services.history.compare(str(base_id), str(head_id))
    except DashboardError as exc:
        html(render_exception(context.palette, exc))
        return

    if not comparison.comparable:
        st.info(comparison.reason)
        return

    delta = comparison.risk_delta
    columns_of(
        [
            metric_card("New findings", str(len(comparison.new))),
            metric_card("Fixed", str(len(comparison.fixed))),
            metric_card("Persisting", str(len(comparison.persisting))),
            metric_card(
                "Risk delta",
                f"{delta:+.1f}",
                # Up is bad for risk. The colour is chosen here because only the caller knows the
                # direction that means "worse" for this particular metric.
                delta=f"{comparison.base.risk_score:.1f} → {comparison.head.risk_score:.1f}",
                delta_colour=context.palette.danger if delta > 0 else context.palette.ok,
            ),
        ]
    )
    for label, rows in (
        ("New", comparison.new),
        ("Fixed", comparison.fixed),
        ("Persisting", comparison.persisting),
    ):
        if rows:
            with st.expander(f"{label} ({len(rows)})"):
                for row in rows:
                    st.write(f"- {row}")
