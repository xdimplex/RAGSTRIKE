"""The page shell: stylesheet injection, headers, banners, and the toast queue.

THE BANNERS ARE NOT DECORATION
    Two of them are load-bearing. **Demo mode** must be impossible to miss, because a screenshot of
    sample findings is indistinguishable from a real assessment. **Backend offline** must be stated
    once at the top rather than nine times as nine separate failures, so the operator knows there is
    one problem and not nine.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from ragstrike.dashboard.components.feedback import banner, toast
from ragstrike.dashboard.components.html import escape, tag
from ragstrike.dashboard.context import PageContext
from ragstrike.dashboard.theme.palette import Palette
from ragstrike.dashboard.theme.styles import stylesheet

DEMO_BANNER = (
    "DEMO MODE — every figure on this screen is fixed sample data. "
    "Nothing here was measured, and none of it is evidence about any system."
)

OFFLINE_BANNER = (
    "BACKEND OFFLINE — the dashboard cannot reach the RAGStrike API, so nothing on this screen is "
    "live. Start the API, or set RAGSTRIKE_DASHBOARD__TRANSPORT=demo to explore the interface."
)


def _write(html: str) -> None:
    import streamlit as st

    st.markdown(html, unsafe_allow_html=True)


def inject_theme(palette: Palette) -> None:
    """Write the stylesheet for the active theme.

    Called once per re-run, before anything else renders. Streamlit has no stylesheet lifecycle, so
    "inject on every run" is the only arrangement that survives a theme change mid-session.
    """
    _write(stylesheet(palette))


def page_header(title: str, subtitle: str = "") -> None:
    """The title block at the top of a page."""
    body = tag("div", escape(title), class_="rs-header__title")
    if subtitle:
        body += tag("div", escape(subtitle), class_="rs-header__sub")
    _write(tag("div", body, class_="rs-header"))


def section(label: str) -> None:
    """A group heading inside a page: a label sitting on a rule.

    Uses ``rs-section`` rather than a bare label with hand-written margins. The rule is what makes
    a dense page readable -- it bounds each group of controls the way a labelled block does in an
    engineering tool, so the eye can find the region it wants without reading every heading.
    """
    _write(tag("div", escape(label), class_="rs-section"))


def rail(items: list[tuple[str, str]]) -> None:
    """A horizontal strip of key/value readouts, under the page header.

    The status rail a tool carries under its toolbar: target, profile, coverage, duration -- the
    facts an operator wants visible at all times without opening anything. Values render monospaced
    so figures line up between pages.
    """
    if not items:
        return
    cells = "".join(
        tag(
            "div",
            tag("div", escape(label), class_="rs-rail__label")
            + tag("div", escape(str(value)), class_="rs-rail__value"),
            class_="rs-rail__item",
        )
        for label, value in items
    )
    _write(tag("div", cells, class_="rs-rail"))


def render_banners(context: PageContext) -> None:
    """Draw the persistent state banners, worst first."""
    if context.demo:
        _write(banner(context.palette, "warning", DEMO_BANNER))
    elif not context.backend_online:
        _write(banner(context.palette, "error", OFFLINE_BANNER))


def render_notifications(context: PageContext) -> None:
    """Drain and draw queued toasts.

    Draining is what stops a toast from reappearing on every re-run -- which, given that Streamlit
    re-runs on every click, is otherwise the default behaviour and reads as the app being stuck.
    """
    for note in context.state.drain_notifications():
        _write(toast(context.palette, note.level, note.message, note.detail))


@contextmanager
def error_boundary(context: PageContext) -> Iterator[None]:
    """Catch anything a page raises and render it as a friendly panel.

    Without this, an exception in one page's body takes out the whole Streamlit script -- including
    the sidebar -- and the operator loses the ability to navigate away from the broken page. This is
    the difference between "the Reports page is failing" and "the dashboard is down".
    """
    from ragstrike.dashboard.components.feedback import render_exception

    try:
        yield
    except Exception as exc:  # the whole point of a boundary is to catch everything
        _write(render_exception(context.palette, exc))


def html(markup: str) -> None:
    """Write a component's output. The single place ``unsafe_allow_html`` is used from a page."""
    _write(markup)


def columns_of(markup: list[str], *, per_row: int = 4) -> None:
    """Lay a list of card fragments out in a responsive grid.

    Streamlit columns do not wrap, so a list of nine cards asked for in one row renders nine
    unreadable slivers. Chunking here is what makes the metric strip degrade sensibly on a narrow
    window rather than shrinking to fit.
    """
    import streamlit as st

    for start in range(0, len(markup), per_row):
        chunk = markup[start : start + per_row]
        for column, fragment in zip(st.columns(len(chunk)), chunk, strict=False):
            with column:
                _write(fragment)
