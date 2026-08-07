"""System Status -- subsystem health, versions, and host resources.

RESPONSIBILITY
    Answer "is the machinery working" for the eight subsystems the brief names.

UNKNOWN IS NOT OK
    Every subsystem gets a row whether or not the backend mentioned it. One that goes unreported
    shows as ``unknown`` with that word on it, because a subsystem that quietly vanishes from the
    page reads as healthy and means the opposite.

CPU AND MEMORY ARE THE BACKEND'S
    Measured by the engine and reported over the API. Measuring them here would report the Streamlit
    server's usage, which in the shipped compose file is a different container -- a precise number
    about the wrong process.
"""

from __future__ import annotations

from ragstrike.dashboard.components.cards import metric_card, status_card, summary_card
from ragstrike.dashboard.components.feedback import empty_state
from ragstrike.dashboard.components.progress import format_duration, progress_bar
from ragstrike.dashboard.context import PageContext
from ragstrike.dashboard.layouts.page_layout import columns_of, html, page_header, section
from ragstrike.dashboard.services.errors import DashboardError
from ragstrike.dashboard.services.models import SystemStatus

OVERALL_MESSAGE = {
    "ok": ("success", "All subsystems reporting healthy."),
    "degraded": ("warning", "At least one subsystem is degraded."),
    "down": ("error", "At least one subsystem is down."),
    "unknown": ("warning", "Subsystem health could not be determined."),
}


def render(context: PageContext) -> None:
    page_header("System Status", "Subsystem health, versions, and host resources.")

    import streamlit as st

    if st.button("Refresh", key="rs.status.refresh"):
        context.state.advance_poll()
        st.rerun()

    try:
        status = context.services.status.status()
    except DashboardError as exc:
        from ragstrike.dashboard.components.feedback import render_exception

        html(render_exception(context.palette, exc))
        return

    _overall(status)
    _components(context, status)
    _resources(context, status)
    _versions(context, status)


def _overall(status: SystemStatus) -> None:
    import streamlit as st

    level, message = OVERALL_MESSAGE.get(status.overall, OVERALL_MESSAGE["unknown"])
    getattr(st, {"success": "success", "warning": "warning", "error": "error"}[level])(message)
    if status.checked_at:
        st.caption(f"Checked at {status.checked_at}")


def _components(context: PageContext, status: SystemStatus) -> None:
    section("Subsystems")
    columns_of(
        [
            status_card(
                context.palette,
                component.name,
                component.status,
                component.detail,
                meta=" · ".join(
                    part
                    for part in (
                        component.version,
                        f"{component.latency_ms} ms" if component.latency_ms else "",
                    )
                    if part
                ),
            )
            for component in status.components
        ],
        per_row=4,
    )


def _resources(context: PageContext, status: SystemStatus) -> None:
    section("Host resources")
    resources = status.resources
    if not resources.available:
        html(
            empty_state(
                "⬢",
                "Resource usage not reported",
                "The backend does not include CPU and memory in its health response.",
                hint="These are measured by the engine, never by the dashboard process.",
            )
        )
        return

    columns_of(
        [
            metric_card("CPU", f"{resources.cpu_percent:.0f}%")
            + progress_bar(resources.cpu_percent / 100, context.palette.accent),
            metric_card(
                "Memory",
                f"{resources.memory_percent:.0f}%",
                hint=f"{resources.memory_used_mb:,.0f} MB in use",
            )
            + progress_bar(resources.memory_percent / 100, context.palette.info),
            metric_card("Uptime", format_duration(resources.uptime_s)),
        ],
        per_row=3,
    )


def _versions(context: PageContext, status: SystemStatus) -> None:
    section("Versions")
    html(
        summary_card(
            "Reported by the engine",
            {
                "Engine": status.engine_version or "unknown",
                "Plugin API": status.plugin_api_version or "unknown",
                "Scoring model": status.scoring_model_version or "unknown",
                "Transport": context.services.transport.describe(),
            },
            footer="The plugin API version moves independently of the application version "
            "(ADR-015), so a patch release does not signal a break to pack authors.",
        )
    )
