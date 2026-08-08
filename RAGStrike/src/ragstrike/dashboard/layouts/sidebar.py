"""The sidebar: brand, navigation, global search, and the connection indicator.

WHY NAVIGATION IS BUTTONS AND NOT `st.navigation`
    Streamlit's built-in multipage navigation keys off files in a ``pages/`` directory and owns the
    routing. This dashboard already has a route registry that the router, the quick actions on Home,
    and the global-search results all read from. Two sources of truth for "what pages exist" is
    exactly the drift the registry was built to prevent, so the sidebar renders from the registry
    like everything else.
"""

from __future__ import annotations

from dataclasses import replace

from ragstrike.dashboard.assets.branding import TAGLINE, wordmark
from ragstrike.dashboard.components.html import escape, style, tag
from ragstrike.dashboard.context import PageContext
from ragstrike.dashboard.navigation.routes import grouped_routes
from ragstrike.dashboard.services.search import group_by_kind, search

#: The sidebar toggle's widget key, and a shadow key recording what this module last wrote to it.
#: The shadow is what lets an external change (the Settings page) be told apart from a user flip.
_TOGGLE_KEY = "rs.sidebar.theme"
_LAST_PUSHED = "rs.sidebar.theme.pushed"


def _connection_line(context: PageContext) -> str:
    palette = context.palette
    if context.demo:
        return tag(
            "div",
            tag(
                "div",
                escape("demo transport — sample data"),
                class_="rs-metric__hint",
                style=style({"color": palette.warn}),
            ),
            class_="rs-conn",
        )
    colour = palette.ok if context.backend_online else palette.danger
    label = "connected" if context.backend_online else "offline"
    # Wrapped in `rs-conn` so the two lines are a flex column with a gap. Emitted as bare siblings
    # they had no spacing of their own and landed on top of the tagline above them.
    return tag(
        "div",
        tag(
            "div",
            tag("span", "●", style=style({"color": colour})) + escape(f" {label}"),
            class_="rs-metric__hint",
        )
        + tag(
            "div",
            escape(context.services.transport.describe()),
            class_="rs-metric__hint",
            style=style({"word-break": "break-all"}),
        ),
        class_="rs-conn",
    )


def render_sidebar(context: PageContext) -> str:
    """Draw the sidebar and return the page id the operator wants.

    Returns the id rather than navigating itself, so the caller decides when the switch takes effect
    -- which keeps navigation out of the middle of a half-rendered page.
    """
    import streamlit as st

    selected = context.state.current_page or "home"

    with st.sidebar:
        st.markdown(
            wordmark(context.palette.accent, context.palette.text, subtitle=TAGLINE),
            unsafe_allow_html=True,
        )
        st.markdown(_connection_line(context), unsafe_allow_html=True)
        st.divider()

        query = st.text_input(
            "Search",
            value=context.state.search_query,
            key="rs.sidebar.search",
            placeholder="Search targets, plugins, scans...",
            label_visibility="collapsed",
        )
        context.state.search_query = str(query or "")
        if context.state.search_query:
            selected = _render_search_results(context, selected)

        st.divider()
        for group, routes in grouped_routes():
            st.markdown(
                tag("div", escape(group), class_="rs-label", style="margin-top:6px"),
                unsafe_allow_html=True,
            )
            for route in routes:
                disabled = route.needs_backend and not context.backend_online and not context.demo
                if st.button(
                    f"{route.icon}  {route.title}",
                    key=f"rs.nav.{route.id}",
                    width="stretch",
                    type="primary" if route.id == selected else "secondary",
                    disabled=disabled,
                    help=route.summary if not disabled else f"{route.summary} (needs the backend)",
                ):
                    selected = route.id

        _render_theme_toggle(context)

    return selected


def _render_theme_toggle(context: PageContext) -> None:
    """The dark/light switch.

    In the sidebar rather than buried in Settings because it is reachable from every section, and
    because an operator who lands on a theme they cannot read should not have to navigate to fix it.

    The choice is written to ``state.settings`` -- the same store the Settings page's theme control
    uses, deliberately, so there is one source of truth. ``build_context`` reads it on every run and
    ``sync_to_url`` mirrors it into the query string, so a change takes effect on the next re-render
    and survives a browser refresh.
    """
    import streamlit as st

    st.divider()
    authoritative_dark = context.config.theme != "light"

    # Keep the widget in step with the setting when something ELSE changed it -- the Settings page
    # has its own theme control. A Streamlit widget with a key ignores `value=` once it has state,
    # so without this the sidebar's stale value would silently win and undo the Settings choice.
    # `_LAST_PUSHED` records what this function last wrote, which is what makes an external change
    # distinguishable from a genuine flip of the switch.
    if st.session_state.get(_LAST_PUSHED) != authoritative_dark:
        st.session_state[_TOGGLE_KEY] = authoritative_dark
        st.session_state[_LAST_PUSHED] = authoritative_dark

    wants_dark = st.toggle(
        "Dark theme",
        key=_TOGGLE_KEY,
        help="Applies to the whole console and is remembered across a refresh.",
    )
    if wants_dark != authoritative_dark:
        context.state.settings = replace(
            context.config, theme="dark" if wants_dark else "light"
        )
        st.session_state[_LAST_PUSHED] = wants_dark
        # Re-run so the stylesheet is rebuilt from the new palette. Without this the toggle would
        # only take effect on the operator's *next* interaction, which reads as a broken switch.
        st.rerun()


def _render_search_results(context: PageContext, selected: str) -> str:
    """Draw global-search hits grouped by kind. Clicking one navigates."""
    import streamlit as st

    hits = search(context.state.search_query, context.services.search_sources(), limit=12)
    if not hits:
        st.caption("No matches.")
        return selected

    for kind, group in group_by_kind(hits):
        st.markdown(
            tag("div", escape(f"{kind}s"), class_="rs-label", style="margin-top:8px"),
            unsafe_allow_html=True,
        )
        for hit in group:
            label = hit.title if not hit.subtitle else f"{hit.title} — {hit.subtitle}"
            if st.button(
                label[:44],
                key=f"rs.hit.{kind}.{hit.id}",
                width="stretch",
                help=hit.subtitle,
            ):
                selected = hit.page_id
                # Remember what the operator clicked, so the destination page can highlight it
                # rather than making them find it again in a list of forty.
                if kind == "target":
                    context.state.current_target = hit.id
                elif kind == "report":
                    context.state.selected_report = hit.id
    return selected
