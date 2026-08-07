"""Feedback surfaces: empty states, toasts, loading overlays, and error panels.

WHY THE EMPTY STATE IS A REAL COMPONENT
    Most of this dashboard is empty most of the time -- no scans yet, no reports yet, no backend yet.
    An empty region with nothing in it is indistinguishable from a broken one, so every list renders
    an empty state that says which of those it is and what to do next. That single decision is most
    of what the brief's ERROR HANDLING section is asking for.
"""

from __future__ import annotations

from ragstrike.dashboard.components.html import escape, join, style, tag
from ragstrike.dashboard.services.errors import DashboardError, FriendlyError
from ragstrike.dashboard.theme.palette import Palette

#: Toast level to palette attribute.
LEVEL_COLOURS: dict[str, str] = {
    "success": "ok",
    "info": "info",
    "warning": "warn",
    "error": "danger",
}


def empty_state(icon: str, title: str, body: str = "", *, hint: str = "") -> str:
    """The "nothing here, and here is why" panel."""
    parts = [
        tag("div", escape(icon), class_="rs-empty__icon"),
        tag("div", escape(title), class_="rs-empty__title"),
    ]
    if body:
        parts.append(tag("div", escape(body), class_="rs-empty__body"))
    if hint:
        parts.append(
            tag("div", escape(hint), class_="rs-metric__hint", style=style({"margin-top": "8px"}))
        )
    return tag("div", join(parts), class_="rs-empty")


def toast(palette: Palette, level: str, message: str, detail: str = "") -> str:
    """A queued notification."""
    colour = str(getattr(palette, LEVEL_COLOURS.get(level.lower(), "info")))
    body = tag("div", escape(message), style=style({"color": palette.text, "font-weight": "600"}))
    extra = tag("div", escape(detail), class_="rs-metric__hint") if detail else ""
    return tag("div", body + extra, class_="rs-toast", style=style({"color": colour}))


def loading_overlay(message: str = "Working...") -> str:
    """A blocking-looking indicator for an operation that is not instant."""
    return tag(
        "div",
        tag("span", "", class_="rs-overlay__spinner") + tag("span", escape(message)),
        class_="rs-overlay",
    )


def banner(palette: Palette, level: str, message: str) -> str:
    """A persistent notice at the top of a page -- demo mode, backend offline, degraded subsystem."""
    colour = str(getattr(palette, LEVEL_COLOURS.get(level.lower(), "info")))
    return tag("div", escape(message), class_="rs-banner", style=style({"color": colour}))


def error_panel(palette: Palette, error: FriendlyError) -> str:
    """The one way a failure reaches the screen.

    Title, plain sentence, and a next step. Every path that can fail routes through here, so an
    operator sees the same shape whatever broke -- and a failure without a remedy is visibly a gap
    in the error taxonomy rather than something to shrug at.
    """
    colour = str(getattr(palette, LEVEL_COLOURS.get(error.severity.lower(), "danger")))
    parts = [
        tag("div", escape(error.title), class_="rs-card__title", style=style({"color": colour})),
        tag("div", escape(error.message), class_="rs-card__body"),
    ]
    if error.remedy:
        parts.append(tag("div", escape(error.remedy), class_="rs-card__foot"))
    return tag(
        "div",
        join(parts),
        class_="rs-card rs-card--accented",
        style=style({"border-left-color": colour}),
    )


def render_exception(palette: Palette, exc: Exception) -> str:
    """Render any exception, mapping the unknown ones onto the same panel.

    An unexpected exception still becomes a friendly panel rather than a Streamlit traceback, and it
    keeps the exception type in the message so a bug report has something to go on.
    """
    if isinstance(exc, DashboardError):
        return error_panel(palette, exc.friendly())
    return error_panel(
        palette,
        FriendlyError(
            title="Unexpected error",
            message=f"{type(exc).__name__}: {exc}",
            remedy="This is a bug in the dashboard. The details above identify where.",
        ),
    )
