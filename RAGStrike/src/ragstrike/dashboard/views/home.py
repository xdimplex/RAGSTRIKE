"""Dashboard Home -- posture overview, recent findings, quick actions, recent activity.

RESPONSIBILITY
    Answer "what is the state of things" in one screen, and offer the two or three actions an
    operator most often wants next. It computes nothing: every number here is read from a service.
"""

from __future__ import annotations

from ragstrike.dashboard.components.badges import grade_hero
from ragstrike.dashboard.components.cards import metric_card, summary_card
from ragstrike.dashboard.components.feedback import empty_state
from ragstrike.dashboard.components.progress import format_duration, severity_bars
from ragstrike.dashboard.components.timeline import TimelineEvent, timeline
from ragstrike.dashboard.context import PageContext
from ragstrike.dashboard.layouts.page_layout import columns_of, html, page_header, section
from ragstrike.dashboard.services.errors import DashboardError
from ragstrike.dashboard.widgets.charts import render_trend_chart

QUICK_ACTIONS: tuple[tuple[str, str, str], ...] = (
    ("▶  New scan", "scan_center", "Configure and launch a scan."),
    ("◇  Targets", "targets", "Review what is configured and reachable."),
    ("▤  Reports", "reports", "Open or export a generated report."),
    ("⬢  System status", "system_status", "Check subsystem health."),
)


def render(context: PageContext) -> None:
    page_header("Dashboard", "Posture across every configured target.")

    if not context.backend_online and not context.demo:
        html(
            empty_state(
                "◎",
                "Nothing to show yet",
                "The dashboard has no backend to read from.",
                hint="Every page works the moment the API is reachable.",
            )
        )
        _quick_actions(context)
        return

    _metrics(context)
    _posture(context)
    _activity(context)
    _quick_actions(context)


def _metrics(context: PageContext) -> None:
    services = context.services
    try:
        targets = services.targets.list_targets()
        inventory = services.plugins.inventory()
        scans = services.history.list_scans()
        versions = services.status.versions()
    except DashboardError as exc:
        html(_panel(context, exc))
        return

    completed = [scan for scan in scans if scan.state == "completed"]
    last = completed[0] if completed else None

    columns_of(
        [
            metric_card(
                "Framework version",
                versions.engine or "unknown",
                hint=f"plugin API {versions.plugin_api}" if versions.plugin_api else "",
            ),
            metric_card(
                "Status",
                "demo" if context.demo else ("online" if context.backend_online else "offline"),
                hint=context.services.transport.describe(),
            ),
            metric_card(
                "Targets",
                str(len(targets)),
                hint=f"{sum(1 for t in targets if t.enabled)} enabled",
            ),
            metric_card(
                "Plugins",
                str(len(inventory.all)),
                hint=f"{len(inventory.active)} active · {len(inventory.rejected)} refused",
            ),
            metric_card("Completed scans", str(len(completed))),
            metric_card(
                "Last scan",
                last.target if last else "--",
                hint=(
                    f"{last.grade or '--'} · {format_duration(last.duration_s)}"
                    if last
                    else "none yet"
                ),
            ),
        ]
    )


def _posture(context: PageContext) -> None:
    try:
        scans = context.services.history.list_scans()
    except DashboardError as exc:
        html(_panel(context, exc))
        return

    completed = [scan for scan in scans if scan.state == "completed"]
    if not completed:
        section("Recent findings")
        html(empty_state("◷", "No completed scans yet", "Launch one from Scan Center."))
        return

    latest = completed[0]
    section("Latest result")

    import streamlit as st

    left, middle, right = st.columns([1, 2, 2])
    with left:
        html(grade_hero(context.palette, latest.grade, coverage=latest.coverage or 1.0))
    with middle:
        html(
            summary_card(
                latest.target or latest.id,
                {
                    "Scan": latest.id,
                    "Profile": latest.profile,
                    "Risk": f"{latest.risk_score:.1f} / 100",
                    "Findings": str(latest.findings_count),
                    "Duration": format_duration(latest.duration_s),
                },
                footer=latest.started_at,
            )
        )
    with right:
        bars = severity_bars(context.palette, latest.severity_counts)
        html(bars or empty_state("—", "No severity breakdown", "The scan recorded no findings."))

    target = latest.target
    if target:
        section(f"Risk trend — {target}")
        render_trend_chart(context.palette, context.services.history.trend(target))


def _activity(context: PageContext) -> None:
    try:
        scans = context.services.history.list_scans()
    except DashboardError as exc:
        html(_panel(context, exc))
        return

    section("Recent activity")
    events = [
        TimelineEvent(
            title=f"{scan.id} — {scan.target}",
            timestamp=scan.started_at,
            detail=f"{scan.outcome or scan.state.upper()} · risk {scan.risk_score:.1f} · "
            f"{scan.findings_count} findings",
            kind=scan.outcome.lower() if scan.outcome else scan.state,
        )
        for scan in scans[:8]
    ]
    html(timeline(context.palette, events) or empty_state("◷", "No activity yet"))


def _quick_actions(context: PageContext) -> None:
    import streamlit as st

    section("Quick actions")
    for column, (label, page_id, help_text) in zip(
        st.columns(len(QUICK_ACTIONS)), QUICK_ACTIONS, strict=True
    ):
        with column, st.container():
            if st.button(label, key=f"rs.home.{page_id}", width="stretch", help=help_text):
                context.navigate(page_id)
                st.rerun()


def _panel(context: PageContext, exc: Exception) -> str:
    from ragstrike.dashboard.components.feedback import render_exception

    return render_exception(context.palette, exc)
