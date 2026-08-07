"""The one place a session-state key is spelled.

WHY AN ENUM AND NOT STRING LITERALS
    ``st.session_state["current_scan"]`` and ``st.session_state["current_scan_id"]`` are two states
    that look like one. The brief's "Do not duplicate state" is only enforceable if there is a
    closed set of keys, and :data:`STATE_KEYS` is that set -- a test asserts nothing outside it is
    ever written.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class StateKey(StrEnum):
    """Every key the dashboard is allowed to keep between re-runs.

    ``StrEnum`` so the member is usable directly as a dictionary key -- Streamlit's session state is
    a string-keyed mapping and will not accept a plain ``Enum``.
    """

    # -- navigation -------------------------------------------------------------------------------
    CURRENT_PAGE = "rs.current_page"

    # -- the seven the brief names ---------------------------------------------------------------
    CURRENT_SCAN = "rs.current_scan"
    CURRENT_TARGET = "rs.current_target"
    LOADED_PLUGINS = "rs.loaded_plugins"
    SELECTED_REPORT = "rs.selected_report"
    SETTINGS = "rs.settings"
    PREFERENCES = "rs.preferences"

    # -- transient UI ----------------------------------------------------------------------------
    #: Queued toasts. Written by any page, drained once by the layout on the next render.
    NOTIFICATIONS = "rs.notifications"
    #: The pending destructive action awaiting confirmation, keyed by dialog id.
    PENDING_CONFIRMATION = "rs.pending_confirmation"
    #: Global search query, shared by the sidebar box and the search results panel.
    SEARCH_QUERY = "rs.search_query"
    #: Active filter selections, one entry per page that has a filter panel.
    FILTERS = "rs.filters"
    #: Monotonic counter bumped on every poll; pages read it to know a refresh happened.
    POLL_TICK = "rs.poll_tick"
    #: Cached plugin inventory plus the tick it was fetched at, so the plugin refresh interval is
    #: honoured without a second copy of the plugin list living on the page.
    PLUGIN_CACHE = "rs.plugin_cache"
    #: The wired service container. Held for the session so the HTTP connection pool survives a
    #: re-run; rebuilt when the transport configuration changes.
    SERVICES = "rs.services"
    #: (monotonic timestamp, reachable) from the last backend probe. Cached so nine pages in one
    #: re-run do not each open a socket to answer the same question.
    BACKEND_HEALTH = "rs.backend_health"


STATE_KEYS: Final[frozenset[str]] = frozenset(key.value for key in StateKey)
