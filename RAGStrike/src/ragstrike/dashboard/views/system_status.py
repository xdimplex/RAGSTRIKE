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

from ragstrike.dashboard.components.cards import status_card, summary_card
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


# THE "HOST RESOURCES" PANEL WAS REMOVED.
#
# It could only ever say "Resource usage not reported". The engine does not put CPU or memory in its
# health response -- ``grep -rn cpu_percent src/ragstrike/api`` finds nothing -- so the panel drew a
# heading, a placeholder icon and an apology, on every load, forever.
#
# WHY NOT IMPLEMENT IT INSTEAD
#   The honest reading is that it would be a new feature, not a repair: it needs a process-metrics
#   dependency and a new field on the health contract.
#
#   Measuring from the dashboard process was the tempting shortcut and is the wrong number. The
#   dashboard is a thin HTTP client; the work happens in the engine. A CPU gauge showing the
#   dashboard idling at 2% while a scan saturates the machine would be worse than no gauge, which is
#   exactly what the panel's own hint said before it was deleted.
#
# The health grid above still reports every subsystem, which is what this page is for.


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
