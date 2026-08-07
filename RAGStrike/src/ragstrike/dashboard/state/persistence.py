"""Session state that survives a browser refresh.

THE PROBLEM
    ``st.session_state`` lives in the server-side session and is discarded the moment the browser
    reloads, the websocket drops, or the tab is reopened. So an operator who set the theme to light,
    navigated to Scan History, filtered to one target, and then pressed F5 was returned to the
    default theme, the Dashboard page, and an unfiltered table -- losing everything they had set up.

    Navigating BETWEEN sections was already safe (session state survives a re-run). Refresh was not,
    and neither was reopening the tab.

THE MECHANISM
    A short allow-list of durable values is mirrored into the URL's query string, which the browser
    keeps across a refresh and which can be bookmarked and shared. On every run the URL is read
    first and merged into session state; when a value changes, the URL is rewritten.

WHY THE URL AND NOT LOCAL STORAGE OR A COOKIE
    It needs no JavaScript component, no extra dependency, and no storage permission -- and it makes
    the state visible and shareable, which is a feature for a security console: "the view I am
    looking at" becomes a link a colleague can open.

WHAT IS DELIBERATELY *NOT* PERSISTED
    Anything large, sensitive, or fast-moving. Notifications, cached service objects, backend health,
    poll ticks, and in-flight scan handles all stay in session state only:

    * a URL is written to browser history and server logs, so nothing sensitive belongs in it;
    * a stale scan handle restored from a bookmark would point at a scan that finished hours ago;
    * URLs have practical length limits, so caches are out.

    The rule is: persist what an operator *chose*, never what the system *computed*.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any, cast

from ragstrike.dashboard.state.keys import StateKey

#: The allow-list: state key -> short query-parameter name.
#:
#: Short names because they are visible in the address bar, and an allow-list rather than a
#: deny-list because the safe default for a new piece of state is "not in the URL". Adding one is a
#: deliberate act.
PERSISTED: Mapping[StateKey, str] = {
    StateKey.CURRENT_PAGE: "page",
    StateKey.CURRENT_TARGET: "target",
    StateKey.SEARCH_QUERY: "q",
    StateKey.SELECTED_REPORT: "report",
}

#: The theme is stored separately from :class:`~ragstrike.dashboard.state.store.AppState` because it
#: is read before the state object exists -- the stylesheet has to be injected first.
THEME_PARAM = "theme"

#: Values equal to these are treated as "unset" and dropped from the URL, so a default choice does
#: not clutter the address bar.
_EMPTY = ("", None)


def restore(state: MutableMapping[str, Any], params: Mapping[str, Any]) -> None:
    """Merge persisted URL values into *state*.

    Session state wins where it already holds a value: within a live session the operator's most
    recent action is more current than the URL, which is only rewritten at the end of a run. The URL
    is therefore a *seed* for a fresh session, not a continuous source of truth.
    """
    for key, param in PERSISTED.items():
        if state.get(key.value) not in _EMPTY:
            continue
        value = _single(params.get(param))
        if value not in _EMPTY:
            state[key.value] = value


def snapshot(state: Mapping[str, Any]) -> dict[str, str]:
    """The query parameters that represent *state*'s durable values."""
    out: dict[str, str] = {}
    for key, param in PERSISTED.items():
        value = state.get(key.value)
        if value not in _EMPTY and isinstance(value, str | int | float | bool):
            out[param] = str(value)
    return out


def restore_theme(params: Mapping[str, Any], default: str) -> str:
    """The theme name from the URL, or *default*.

    Validated against the known palettes by the caller; an unknown name there falls back rather than
    raising, so a hand-edited URL cannot break the page.
    """
    value = _single(params.get(THEME_PARAM))
    return str(value) if value not in _EMPTY else default


def _single(value: Any) -> Any:
    """Query parameters may arrive as a list. Take the first, which is what a browser sends."""
    if isinstance(value, list | tuple):
        return value[0] if value else None
    return value


# --------------------------------------------------------------------------------------------------
# The Streamlit-facing helpers. Split out so everything above is testable with plain dicts.
# --------------------------------------------------------------------------------------------------


def load_into_session() -> None:
    """Seed ``st.session_state`` from the URL. Call once, before anything reads state."""
    import streamlit as st

    # `SessionStateProxy` is mapping-like but is not declared as a MutableMapping, so the cast
    # is where that equivalence is asserted rather than assumed.
    restore(cast("MutableMapping[str, Any]", st.session_state), dict(st.query_params))


def sync_to_url() -> None:
    """Write the durable slice of session state back to the URL.

    Only writes when something actually changed. Streamlit re-runs the script on every interaction,
    and assigning to ``st.query_params`` unconditionally would rewrite history on every keystroke.
    """
    import streamlit as st

    desired = snapshot(cast("Mapping[str, Any]", st.session_state))
    # The theme lives on the settings object rather than in the state mapping, so it is read
    # separately. `getattr` because that slot holds a DashboardConfig, not a dict.
    settings = st.session_state.get(StateKey.SETTINGS.value)
    theme = getattr(settings, "theme", "")
    if theme:
        desired[THEME_PARAM] = str(theme)

    current = {k: _single(v) for k, v in dict(st.query_params).items()}
    if current != desired:
        st.query_params.clear()
        for key, value in desired.items():
            st.query_params[key] = value
