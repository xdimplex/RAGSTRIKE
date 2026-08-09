"""The typed accessor over Streamlit's session state.

DESIGN
    :class:`AppState` wraps *any* mutable string-keyed mapping. In the app that mapping is
    ``st.session_state``; in tests it is a plain ``dict``. That one indirection is why the state
    layer is exhaustively testable without starting a Streamlit server, and it costs nothing at
    runtime.

THE INVARIANT
    Every write goes through a property or a method on this class, and every one of those uses a
    :class:`~ragstrike.dashboard.state.keys.StateKey`. No page indexes the mapping directly. That is
    what makes "do not duplicate state" checkable rather than aspirational.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass, field
from typing import Any, TypeVar, cast

from ragstrike.dashboard.config import DashboardConfig, load_config
from ragstrike.dashboard.state.keys import StateKey

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Notification:
    """A queued toast. Drained by the layout, never rendered by the page that raised it."""

    level: str
    message: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ScanHandle:
    """What the UI remembers about the scan it is watching.

    Deliberately *not* a copy of the scan: only the id and the last-known state live here. Scan
    detail is refetched every poll, because a cached copy of a running scan is by definition stale
    and would be the single most misleading thing on the screen.
    """

    scan_id: str
    target: str = ""
    #: The operator's label for this run, so the live panel can head itself with something readable
    #: instead of 32 characters of hex.
    name: str = ""
    state: str = "queued"
    started_at: str = ""


@dataclass(slots=True)
class AppState:
    """Typed, key-checked access to one session's state."""

    raw: MutableMapping[str, Any] = field(default_factory=dict)

    # -- primitives -------------------------------------------------------------------------------

    def get(self, key: StateKey, default: T) -> T:
        value = self.raw.get(key.value, default)
        # A session that survived a code change can hold a value of the previous shape. Falling back
        # to the default beats raising on a page the operator opened to diagnose something else.
        return value if isinstance(value, type(default)) else default

    def set(self, key: StateKey, value: object) -> None:
        self.raw[key.value] = value

    def clear(self, key: StateKey) -> None:
        self.raw.pop(key.value, None)

    def has(self, key: StateKey) -> bool:
        return key.value in self.raw

    # -- navigation -------------------------------------------------------------------------------

    @property
    def current_page(self) -> str:
        return self.get(StateKey.CURRENT_PAGE, "")

    @current_page.setter
    def current_page(self, page_id: str) -> None:
        self.set(StateKey.CURRENT_PAGE, page_id)

    # -- the working set --------------------------------------------------------------------------

    @property
    def current_scan(self) -> ScanHandle | None:
        value = self.raw.get(StateKey.CURRENT_SCAN.value)
        return value if isinstance(value, ScanHandle) else None

    @current_scan.setter
    def current_scan(self, handle: ScanHandle | None) -> None:
        if handle is None:
            self.clear(StateKey.CURRENT_SCAN)
        else:
            self.set(StateKey.CURRENT_SCAN, handle)

    @property
    def current_target(self) -> str:
        return self.get(StateKey.CURRENT_TARGET, "")

    @current_target.setter
    def current_target(self, name: str) -> None:
        self.set(StateKey.CURRENT_TARGET, name)

    @property
    def selected_report(self) -> str:
        return self.get(StateKey.SELECTED_REPORT, "")

    @selected_report.setter
    def selected_report(self, report_id: str) -> None:
        self.set(StateKey.SELECTED_REPORT, report_id)

    @property
    def loaded_plugins(self) -> list[str]:
        """Slugs the operator has selected for the next scan.

        The *inventory* is not stored here -- that is the plugin service's job and it is cached
        under :attr:`StateKey.PLUGIN_CACHE`. Keeping the selection separate from the inventory is
        what stops a stale selection from resurrecting a plugin that has since been uninstalled.
        """
        return list(self.get(StateKey.LOADED_PLUGINS, []))

    @loaded_plugins.setter
    def loaded_plugins(self, slugs: list[str]) -> None:
        self.set(StateKey.LOADED_PLUGINS, list(dict.fromkeys(slugs)))

    # -- configuration ----------------------------------------------------------------------------

    @property
    def settings(self) -> DashboardConfig:
        """The effective configuration for this session.

        Loaded from the environment on first access, then owned by the session so the settings page
        can change it without touching the process environment.
        """
        value = self.raw.get(StateKey.SETTINGS.value)
        if not isinstance(value, DashboardConfig):
            value = load_config()
            self.set(StateKey.SETTINGS, value)
        return value

    @settings.setter
    def settings(self, config: DashboardConfig) -> None:
        self.set(StateKey.SETTINGS, config)

    @property
    def preferences(self) -> dict[str, Any]:
        """Free-form per-user UI choices: expanded panels, table density, last-used filters.

        Distinct from :attr:`settings`, which is configuration the backend or the environment could
        also supply. Preferences never affect what a scan does.
        """
        value = self.raw.setdefault(StateKey.PREFERENCES.value, {})
        return value if isinstance(value, dict) else {}

    # -- transient --------------------------------------------------------------------------------

    def notify(self, level: str, message: str, detail: str = "") -> None:
        """Queue a toast for the next render."""
        queue = list(self.get(StateKey.NOTIFICATIONS, []))
        queue.append(Notification(level=level, message=message, detail=detail))
        self.set(StateKey.NOTIFICATIONS, queue)

    def drain_notifications(self) -> list[Notification]:
        """Return queued toasts and empty the queue. Draining is what stops a toast repeating on
        every re-run -- which, with Streamlit's re-run model, is otherwise the default."""
        raw: list[object] = self.get(StateKey.NOTIFICATIONS, [])
        queue = [note for note in raw if isinstance(note, Notification)]
        self.clear(StateKey.NOTIFICATIONS)
        return queue

    @property
    def search_query(self) -> str:
        return self.get(StateKey.SEARCH_QUERY, "")

    @search_query.setter
    def search_query(self, query: str) -> None:
        self.set(StateKey.SEARCH_QUERY, query)

    def filters_for(self, page_id: str) -> dict[str, Any]:
        """Filter selections for one page. Each page owns a namespace inside one dictionary, so
        there is still exactly one filter state rather than one per page."""
        store = self.raw.setdefault(StateKey.FILTERS.value, {})
        if not isinstance(store, dict):
            store = {}
            self.set(StateKey.FILTERS, store)
        namespace = store.setdefault(page_id, {})
        return namespace if isinstance(namespace, dict) else {}

    def pending_confirmation(self, dialog_id: str) -> Any:
        store = self.raw.get(StateKey.PENDING_CONFIRMATION.value)
        return store.get(dialog_id) if isinstance(store, dict) else None

    def request_confirmation(self, dialog_id: str, payload: object) -> None:
        store = self.raw.setdefault(StateKey.PENDING_CONFIRMATION.value, {})
        if isinstance(store, dict):
            store[dialog_id] = payload

    def resolve_confirmation(self, dialog_id: str) -> None:
        store = self.raw.get(StateKey.PENDING_CONFIRMATION.value)
        if isinstance(store, dict):
            store.pop(dialog_id, None)

    @property
    def poll_tick(self) -> int:
        return self.get(StateKey.POLL_TICK, 0)

    def advance_poll(self) -> int:
        tick = self.poll_tick + 1
        self.set(StateKey.POLL_TICK, tick)
        return tick


def session_state() -> AppState:
    """Bind :class:`AppState` to Streamlit's real session state.

    The import is inside the function on purpose: it keeps ``ragstrike.dashboard.state`` importable
    -- and therefore testable -- in an environment where Streamlit is not installed, which is the
    case for anyone who installed RAGStrike without the ``[dashboard]`` extra.
    """
    import streamlit as st

    # Streamlit's SessionStateProxy is a MutableMapping in behaviour but does not declare the
    # protocol, so the cast is the honest way to say "this satisfies what AppState needs".
    return AppState(raw=cast("MutableMapping[str, Any]", st.session_state))
