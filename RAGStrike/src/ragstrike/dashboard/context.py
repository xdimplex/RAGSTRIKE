"""The object every page receives.

WHY A CONTEXT OBJECT RATHER THAN MODULE-LEVEL SINGLETONS
    Streamlit re-runs the script on every interaction. Module-level singletons survive that re-run
    and are shared across *every* browser session connected to the same server -- so one operator's
    selected target would leak into another's. Threading a per-session context through explicitly is
    the only arrangement where that cannot happen.

WHAT A PAGE MAY DO WITH IT
    Read services, read and write state, read the palette and the config. A page never constructs a
    service, never chooses a transport, and never touches ``st.session_state`` directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ragstrike.dashboard.config import DashboardConfig
from ragstrike.dashboard.services import Services
from ragstrike.dashboard.state.store import AppState
from ragstrike.dashboard.theme.palette import Palette, palette_for


@dataclass(frozen=True, slots=True)
class PageContext:
    """Everything a page is allowed to reach."""

    services: Services
    state: AppState
    config: DashboardConfig
    #: Whether the backend answered its health check on this re-run. Computed once by the shell so
    #: nine pages do not each make their own probe and each draw their own conclusion.
    backend_online: bool = False
    #: Populated by the shell from the config's theme name.
    palette: Palette = field(default_factory=lambda: palette_for("dark"))

    @property
    def demo(self) -> bool:
        return self.services.is_demo

    def navigate(self, page_id: str) -> None:
        """Move to another page. Takes effect on the next re-run."""
        self.state.current_page = page_id

    def notify(self, level: str, message: str, detail: str = "") -> None:
        self.state.notify(level, message, detail)


def build_context(
    services: Services,
    state: AppState,
    config: DashboardConfig,
    *,
    backend_online: bool,
) -> PageContext:
    return PageContext(
        services=services,
        state=state,
        config=config,
        backend_online=backend_online,
        # Read on every run so a theme change takes effect on the next re-render. `config` here is
        # `state.settings`, which is the SINGLE source of truth for the theme -- both the Settings
        # page and the sidebar toggle write to it. Two stores briefly existed and immediately
        # fought: the sidebar's stored widget value silently overrode the Settings page's choice.
        #
        # `palette_for` falls back to dark on an unknown name, so a stale setting or a hand-edited
        # URL cannot break the page.
        palette=palette_for(config.theme),
    )
