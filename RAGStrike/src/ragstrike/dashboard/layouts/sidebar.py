"""The sidebar: brand, navigation, global search, and the connection indicator.

WHY NAVIGATION IS BUTTONS AND NOT `st.navigation`
    Streamlit's built-in multipage navigation keys off files in a ``pages/`` directory and owns the
    routing. This dashboard already has a route registry that the router, the quick actions on Home,
    and the global-search results all read from. Two sources of truth for "what pages exist" is
    exactly the drift the registry was built to prevent, so the sidebar renders from the registry
    like everything else.
"""

from __future__ import annotations

from ragstrike.dashboard.assets.branding import TAGLINE, wordmark
from ragstrike.dashboard.components.html import escape, style, tag
from ragstrike.dashboard.context import PageContext
from ragstrike.dashboard.navigation.routes import grouped_routes
from ragstrike.dashboard.services.search import group_by_kind, search

# NO THEME TOGGLE. The console is always dark -- see `build_context` for why the choice was
# deleted rather than fixed again.


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

        # ONE FLAT LIST, NO GROUP HEADINGS, NO TOOLTIPS.
        #
        # `help=` put a floating tooltip over the nav on every hover -- "Configured targets, their
        # health, and their authorization records." obscuring the buttons underneath it. A label
        # that covers the thing it describes is worse than no label, and the section names are
        # already self-explanatory.
        #
        # The group headings ("MANAGE") cost a row each and rendered as loose text beside the
        # buttons. Removing them and the headings' margins is what makes all nine sections fit
        # without scrolling, which is the layout in the reference diagram.
        for _group, routes in grouped_routes():
            for route in routes:
                disabled = route.needs_backend and not context.backend_online and not context.demo
                if st.button(
                    f"{route.icon}  {route.title}",
                    key=f"rs.nav.{route.id}",
                    width="stretch",
                    type="primary" if route.id == selected else "secondary",
                    disabled=disabled,
                ):
                    selected = route.id

    return selected



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
