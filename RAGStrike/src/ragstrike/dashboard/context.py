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

from dataclasses import dataclass

from ragstrike.dashboard.config import DashboardConfig
from ragstrike.dashboard.services import Services
from ragstrike.dashboard.state.store import AppState
from ragstrike.dashboard.theme.palette import DARK, Palette


@dataclass(frozen=True, slots=True)
class PageContext:
    """Everything a page is allowed to reach."""

    services: Services
    state: AppState
    config: DashboardConfig
    #: Whether the backend answered its health check on this re-run. Computed once by the shell so
    #: nine pages do not each make their own probe and each draw their own conclusion.
    backend_online: bool = False
    #: The console's only palette. See `build_context` for why there is no longer a choice.
    palette: Palette = DARK

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
        # THE CONSOLE IS DARK. There is no runtime choice, and that is the fix.
        #
        # A light mode existed and was reported as broken five separate times -- always the same
        # symptom, a light page carrying dark widgets. The cause was never one selector: Streamlit
        # compiles its base theme into every native widget, so a second theme means keeping a
        # hand-written stylesheet in step with a compiled one across every widget and every
        # Streamlit release. Each fix closed the gap for the widgets someone had thought of.
        #
        # Deleting the choice deletes the class of bug. A security console that is always dark
        # cannot be half light, and DARK is the right default for one: it is what the operator
        # stares at for the length of a scan.
        palette=DARK,
    )
