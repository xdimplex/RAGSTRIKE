"""Scan Center -- configure, launch, watch, and cancel a scan.

RESPONSIBILITY
    The one page that starts work. Everything else in the dashboard reads; this writes.

THE AUTHORIZATION CHECKBOX
    START SCAN stays disabled until the operator confirms authorization. This is a *second* gate:
    the backend enforces the target's own authorization record independently, and refuses regardless
    of what this page sends. The redundancy is deliberate -- ADR-017 -- because the cost is one
    checkbox and the failure it prevents is scanning a system nobody agreed to have scanned.

LIVE PROGRESS IS POLLED
    One request per re-run, on the configured interval, and it stops the moment the scan reaches a
    terminal state. See :func:`ragstrike.dashboard.services.scan_service.should_poll`.
"""

from __future__ import annotations

from ragstrike.dashboard.components.feedback import empty_state, render_exception
from ragstrike.dashboard.components.log_viewer import log_viewer
from ragstrike.dashboard.components.progress import scan_progress
from ragstrike.dashboard.context import PageContext
from ragstrike.dashboard.layouts.page_layout import html, page_header, section
from ragstrike.dashboard.services.errors import DashboardError
from ragstrike.dashboard.services.scan_service import ScanRequest, should_poll
from ragstrike.dashboard.state.store import ScanHandle
from ragstrike.dashboard.widgets.tables import findings_rows, render_table


def render(context: PageContext) -> None:
    page_header("Scan Center", "Configure a scan, launch it, and watch it run.")

    if not context.backend_online and not context.demo:
        html(
            empty_state("▶", "No backend", "Scans are started by the API, which is not reachable.")
        )
        return

    handle = context.state.current_scan
    if handle is not None:
        _live(context, handle)
        return

    _launcher(context)


# -------------------------------------------------------------------------------------------------
# Launch
# -------------------------------------------------------------------------------------------------


def _launcher(context: PageContext) -> None:
    import streamlit as st

    services = context.services
    try:
        targets = services.targets.list_targets()
        inventory = services.plugins.inventory()
        profiles = services.scans.profiles()
    except DashboardError as exc:
        html(render_exception(context.palette, exc))
        return

    if not targets:
        html(empty_state("◇", "No targets configured", "Add one on the Targets page first."))
        return

    names = [target.name for target in targets]
    default_name = context.state.current_target or context.config.default_target
    index = names.index(default_name) if default_name in names else 0

    left, right = st.columns([3, 2])

    with left:
        section("Target")
        target_name = st.selectbox("Target", names, index=index, key="rs.scan.target")
        context.state.current_target = str(target_name)
        selected_target = next(t for t in targets if t.name == target_name)
        st.caption(f"{selected_target.url} · adapter {selected_target.adapter}")

        section("Configuration")
        scan_name = st.text_input("Scan name", value=f"{target_name} scan", key="rs.scan.name")
        profile_ids = [profile.id for profile in profiles] or ["standard"]
        profile = st.radio(
            "Profile",
            profile_ids,
            horizontal=True,
            key="rs.scan.profile",
            index=profile_ids.index("standard") if "standard" in profile_ids else 0,
        )
        chosen_profile = next((p for p in profiles if p.id == profile), None)
        if chosen_profile and chosen_profile.description:
            st.caption(chosen_profile.description)

        section("Plugins")
        categories = st.multiselect(
            "Categories",
            inventory.categories,
            default=list(inventory.categories),
            key="rs.scan.categories",
            help="Narrowing categories narrows the plugin list below.",
        )
        candidates = [
            plugin for plugin in inventory.active if not categories or plugin.category in categories
        ]
        slugs = st.multiselect(
            "Individual plugins",
            [plugin.slug for plugin in candidates],
            default=[plugin.slug for plugin in candidates if plugin.enabled],
            key="rs.scan.plugins",
        )
        context.state.loaded_plugins = list(slugs)

    with right:
        _plan_summary(context, selected_target, chosen_profile, len(slugs))
        authorized = st.checkbox(
            "I confirm I am authorized to test this target.",
            key="rs.scan.authorized",
            help="RAGStrike also enforces the target's own authorization record; this does not "
            "override it.",
        )
        request = ScanRequest(
            target=str(target_name),
            profile=str(profile),
            name=str(scan_name),
            plugins=tuple(slugs),
            categories=tuple(categories),
            authorized=bool(authorized),
        )
        if st.button(
            "▶  START SCAN",
            key="rs.scan.start",
            type="primary",
            width="stretch",
            disabled=not request.ready,
        ):
            _start(context, request)


def _plan_summary(context: PageContext, target: object, profile: object, plugin_count: int) -> None:
    from ragstrike.dashboard.components.cards import summary_card
    from ragstrike.dashboard.components.progress import format_duration
    from ragstrike.dashboard.services.scan_service import ScanProfile

    section("Plan")
    resolved = profile if isinstance(profile, ScanProfile) else ScanProfile(id="standard")
    cases, seconds = context.services.scans.estimate(resolved, plugin_count)
    health = getattr(target, "health", None)
    capabilities = ", ".join(getattr(health, "capabilities", ()) or ()) or "not probed"
    html(
        summary_card(
            "Estimated",
            {
                "Plugins": str(plugin_count),
                "Cases": str(cases),
                "Duration": f"~{format_duration(seconds)}",
                "Capabilities": capabilities,
            },
            footer="Estimates, not predictions: cases scale with the plugins you selected.",
        )
    )


def _start(context: PageContext, request: ScanRequest) -> None:
    import streamlit as st

    try:
        scan_id = context.services.scans.start(request)
    except DashboardError as exc:
        html(render_exception(context.palette, exc))
        return

    context.state.current_scan = ScanHandle(scan_id=scan_id, target=request.target, state="queued")
    context.notify("success", f"Scan {scan_id} started against {request.target}.")
    st.rerun()


# -------------------------------------------------------------------------------------------------
# Live view
# -------------------------------------------------------------------------------------------------


def _live(context: PageContext, handle: ScanHandle) -> None:
    import streamlit as st

    try:
        progress = context.services.scans.progress(handle.scan_id)
    except DashboardError as exc:
        html(render_exception(context.palette, exc))
        if st.button("Back to launcher", key="rs.scan.back.error"):
            context.state.current_scan = None
            st.rerun()
        return

    context.state.current_scan = ScanHandle(
        scan_id=handle.scan_id,
        target=handle.target,
        state=progress.state,
        started_at=handle.started_at,
    )

    section(f"{handle.scan_id} — {handle.target}")
    html(scan_progress(context.palette, progress))

    controls = st.columns(3)
    if not progress.finished and controls[0].button(
        "Cancel scan", key="rs.scan.cancel", type="secondary"
    ):
        _cancel(context, handle.scan_id)
    if progress.finished and controls[0].button("New scan", key="rs.scan.new", type="primary"):
        context.state.current_scan = None
        st.rerun()
    if progress.finished and controls[1].button("View in history", key="rs.scan.history"):
        context.navigate("scan_history")
        st.rerun()

    _logs(context, handle.scan_id)

    if progress.finished:
        _results(context, handle.scan_id)
        return

    # The one poll per re-run. `should_poll` is what stops this becoming a busy loop the moment the
    # scan finishes.
    if should_poll(progress.state):
        context.state.advance_poll()
        st.caption(f"Refreshing every {context.config.refresh_interval_s:g}s.")
        _schedule_refresh(context.config.refresh_interval_s)


def _schedule_refresh(interval_s: float) -> None:
    """Ask Streamlit to re-run after the poll interval.

    ``st.rerun`` alone would spin as fast as the CPU allows. The sleep is the polling interval, and
    it is bounded by configuration so a mistyped value cannot turn into a hot loop against the API.
    """
    import time

    import streamlit as st

    time.sleep(max(0.5, min(60.0, interval_s)))
    st.rerun()


def _cancel(context: PageContext, scan_id: str) -> None:
    import streamlit as st

    try:
        context.services.scans.cancel(scan_id)
    except DashboardError as exc:
        html(render_exception(context.palette, exc))
        return
    context.notify("warning", f"Scan {scan_id} cancelled.")
    st.rerun()


def _logs(context: PageContext, scan_id: str) -> None:
    import streamlit as st

    with st.expander("Logs", expanded=True):
        try:
            lines = context.services.scans.logs(scan_id)
        except DashboardError as exc:
            html(render_exception(context.palette, exc))
            return
        html(log_viewer(context.palette, lines, minimum_level=context.config.log_level))


def _results(context: PageContext, scan_id: str) -> None:
    section("Findings")
    try:
        findings = context.services.scans.findings(scan_id)
    except DashboardError as exc:
        html(render_exception(context.palette, exc))
        return
    if not findings:
        html(empty_state("✓", "No findings", "The scan completed without producing findings."))
        return
    render_table(findings_rows(findings))
