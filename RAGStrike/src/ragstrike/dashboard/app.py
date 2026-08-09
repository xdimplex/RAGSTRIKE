"""The Streamlit entry point.

RUN IT

    streamlit run src/ragstrike/dashboard/app.py

WHAT THIS MODULE OWNS
    Session bootstrap and the render order, and nothing else. It builds the services once, probes the
    backend once, injects the stylesheet, draws the shell, and hands control to the router. Every
    decision about *what* to display belongs to a page.

WHY THE ORDER MATTERS
    The stylesheet has to be written before any component, the sidebar before the body (it decides
    which page the body is), and the toast queue after the body (so a page can raise a toast in the
    same re-run it was clicked in). Getting this wrong produces a dashboard that flickers unstyled
    and shows notifications one click late.
"""

from __future__ import annotations

from dataclasses import dataclass
import time

from ragstrike.dashboard.config import DashboardConfig
from ragstrike.dashboard.context import build_context
from ragstrike.dashboard.layouts.page_layout import (
    error_boundary,
    inject_theme,
    render_banners,
    render_notifications,
)
from ragstrike.dashboard.layouts.sidebar import render_sidebar
from ragstrike.dashboard.navigation.router import Router
from ragstrike.dashboard.navigation.routes import DEFAULT_ROUTE
from ragstrike.dashboard.services import Services, build_services
from ragstrike.dashboard.state.keys import StateKey
from ragstrike.dashboard.state.persistence import load_into_session, sync_to_url
from ragstrike.dashboard.state.store import AppState, session_state

PAGE_TITLE = "RAGStrike"

#: How long a backend probe is trusted. Short enough that starting the API is noticed within a few
#: seconds, long enough that one re-run does not open nine sockets to answer the same question.
HEALTH_TTL_S = 5.0


@dataclass(frozen=True, slots=True)
class HealthProbe:
    """One cached backend probe. A named pair beats a bare tuple that every reader has to decode."""

    checked_at: float
    reachable: bool


def _services(state: AppState) -> Services:
    """Build the service container once per session, rebuilding if the transport changed.

    Rebuilding on change matters: switching to demo mode in Settings has to take effect without a
    restart, and a stale container would keep talking to a transport the operator has moved away
    from while the banner claimed otherwise.
    """
    config = state.settings
    cached = state.raw.get(StateKey.SERVICES.value)
    if isinstance(cached, Services) and cached.transport.name == config.transport:
        return cached

    if isinstance(cached, Services):
        cached.close()
    services = build_services(config)
    state.set(StateKey.SERVICES, services)
    return services


def _backend_online(state: AppState, services: Services, *, now: float | None = None) -> bool:
    """Probe the backend, cached for :data:`HEALTH_TTL_S`.

    The demo transport always answers, so this is really "is the thing we are talking to alive"
    rather than "is HTTP up" -- which is the question every page actually needs.
    """
    stamp = time.monotonic() if now is None else now
    cached = state.raw.get(StateKey.BACKEND_HEALTH.value)
    if isinstance(cached, HealthProbe) and stamp - cached.checked_at < HEALTH_TTL_S:
        return cached.reachable

    probe = HealthProbe(checked_at=stamp, reachable=services.status.reachable())
    state.set(StateKey.BACKEND_HEALTH, probe)
    return probe.reachable


def configure_page() -> None:
    """Streamlit's own page settings. Must run before anything else renders."""
    import streamlit as st

    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon="◎",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={"About": "RAGStrike — offensive security evaluation for RAG systems."},
    )


def main() -> None:
    """One Streamlit re-run, start to finish."""
    import streamlit as st

    # URL first: session state is discarded on a browser refresh, so anything the operator chose --
    # theme, page, target, search -- has to be seeded from the query string before anything reads
    # it. Without this, F5 returned the operator to the default theme and the Dashboard page.
    load_into_session()

    state = session_state()
    config: DashboardConfig = state.settings

    configure_page()

    services = _services(state)
    context = build_context(
        services, state, config, backend_online=_backend_online(state, services)
    )

    # Stylesheet first: anything rendered before it appears unstyled for a frame.
    inject_theme(context.palette)

    if not state.current_page:
        state.current_page = DEFAULT_ROUTE.id

    # Sidebar before the body, because it is what decides which body to draw.
    selected = render_sidebar(context)
    if selected != state.current_page:
        state.current_page = selected
        # Write the URL BEFORE re-running.
        #
        # `sync_to_url()` lives at the end of this function, and `st.rerun()` never reaches it --
        # so navigation, the one action that most needs recording, was the one action that never
        # updated the address bar. A refresh then returned the operator to whichever page they had
        # been on before the last navigation.
        sync_to_url()
        # Re-run before drawing the body.
        #
        # The sidebar renders top to bottom, so the buttons ABOVE the one just clicked were already
        # drawn -- with the old page still marked active. Clicking "Scan History" therefore left
        # "Reports" highlighted while the Scan History body rendered below it, and the same lag hit
        # every route whose predecessor was the previous selection.
        #
        # Re-running here redraws the sidebar with the new selection before the body appears, which
        # costs one extra pass and makes the highlight always agree with the page on screen.
        st.rerun()

    render_banners(context)

    # The error boundary is what keeps a failing page from taking the sidebar down with it. Without
    # it, an exception in one page leaves the operator with no way to navigate away from it.
    with error_boundary(context):
        resolution = Router().dispatch(state.current_page, context)
        if not resolution.ok:
            raise RuntimeError(
                f"The {resolution.route.title} page could not be loaded: {resolution.error}"
            )

    # Toasts last, so a page can raise one in the same re-run the button was clicked in.
    render_notifications(context)

    # And the URL last of all, once every page and widget has had its say. Writing it earlier would
    # persist a value the page was about to change, so a refresh would restore the state from just
    # *before* the operator's most recent action.
    sync_to_url()


if __name__ == "__main__":  # pragma: no cover - executed by `streamlit run`, not by a test
    main()
