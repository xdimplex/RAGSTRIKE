"""State that survives a browser refresh, and the theme toggle that depends on it.

WHY THESE EXIST
    ``st.session_state`` is discarded on refresh. Every one of these behaviours was reported broken:
    the theme reset, the current section reset, and a filtered view reset -- all on F5, and all
    invisible to the existing suite because AppTest never reloads a browser.

    The functions under test take plain mappings precisely so this can be asserted without a
    Streamlit server: a refresh is just "a fresh dict plus the previous URL".
"""

from __future__ import annotations

from ragstrike.dashboard.config import DashboardConfig
from ragstrike.dashboard.state.keys import StateKey
from ragstrike.dashboard.state.persistence import (
    PERSISTED,
    THEME_PARAM,
    restore,
    restore_theme,
    snapshot,
)
from ragstrike.dashboard.state.store import AppState
from ragstrike.dashboard.theme.palette import palette_for

# -- restore (a refresh) ---------------------------------------------------------------------------


def test_a_refresh_restores_the_section_the_operator_was_on() -> None:
    """The headline bug: F5 returned the operator to the default page."""
    fresh: dict[str, object] = {}

    restore(fresh, {"page": "scan_history"})

    assert fresh[StateKey.CURRENT_PAGE.value] == "scan_history"


def test_a_refresh_restores_the_whole_persisted_set() -> None:
    fresh: dict[str, object] = {}

    restore(fresh, {"page": "targets", "target": "vulnerable-rag", "q": "inject", "report": "r1"})

    assert fresh[StateKey.CURRENT_PAGE.value] == "targets"
    assert fresh[StateKey.CURRENT_TARGET.value] == "vulnerable-rag"
    assert fresh[StateKey.SEARCH_QUERY.value] == "inject"
    assert fresh[StateKey.SELECTED_REPORT.value] == "r1"


def test_a_live_session_beats_a_stale_url() -> None:
    """The URL is a seed for a fresh session, not a continuous source of truth.

    It is rewritten at the END of a run, so mid-session it lags the operator's most recent action.
    Letting it win would undo the click that had just happened.
    """
    live = {StateKey.CURRENT_PAGE.value: "reports"}

    restore(live, {"page": "home"})

    assert live[StateKey.CURRENT_PAGE.value] == "reports"


def test_an_absent_parameter_leaves_state_untouched() -> None:
    fresh: dict[str, object] = {}

    restore(fresh, {})

    assert fresh == {}


def test_a_query_parameter_arriving_as_a_list_takes_the_first_value() -> None:
    """Browsers can send ``?page=a&page=b``; a list must not end up as the state value."""
    fresh: dict[str, object] = {}

    restore(fresh, {"page": ["scan_center", "home"]})

    assert fresh[StateKey.CURRENT_PAGE.value] == "scan_center"


# -- snapshot (what gets written to the URL) -------------------------------------------------------


def test_snapshot_emits_only_the_allow_listed_keys() -> None:
    out = snapshot(
        {
            StateKey.CURRENT_PAGE.value: "targets",
            StateKey.SEARCH_QUERY.value: "acme",
            StateKey.NOTIFICATIONS.value: ["something private"],
            StateKey.BACKEND_HEALTH.value: {"reachable": True},
        }
    )

    assert out == {"page": "targets", "q": "acme"}


def test_nothing_computed_or_sensitive_is_ever_persisted() -> None:
    """A URL reaches browser history and server logs. Only operator CHOICES belong in it."""
    forbidden = {
        StateKey.NOTIFICATIONS,
        StateKey.SERVICES,
        StateKey.BACKEND_HEALTH,
        StateKey.PLUGIN_CACHE,
        StateKey.CURRENT_SCAN,
        StateKey.POLL_TICK,
    }

    assert not (forbidden & set(PERSISTED))


def test_empty_values_are_dropped_rather_than_written_as_blanks() -> None:
    out = snapshot({StateKey.CURRENT_PAGE.value: "home", StateKey.SEARCH_QUERY.value: ""})

    assert out == {"page": "home"}


def test_snapshot_round_trips_through_restore() -> None:
    original = {StateKey.CURRENT_PAGE.value: "plugins", StateKey.CURRENT_TARGET.value: "secure-rag"}

    recovered: dict[str, object] = {}
    restore(recovered, snapshot(original))

    assert recovered == original


# -- the theme -------------------------------------------------------------------------------------


def test_the_theme_survives_a_refresh() -> None:
    assert restore_theme({THEME_PARAM: "light"}, default="dark") == "light"


def test_an_absent_theme_falls_back_to_the_default() -> None:
    assert restore_theme({}, default="dark") == "dark"


def test_the_palette_is_fixed_and_ignores_settings() -> None:
    """The console is DARK, and no setting can change that.

    A light mode existed and was reported broken five times, always as "half light, half dark".
    Streamlit compiles its base theme into every native widget, so a second theme means keeping a
    hand-written stylesheet in step with a compiled one forever; each fix covered the widgets
    someone had thought of.

    Removing the choice removes the class of bug. This asserts a stale stored preference -- or a
    hand-edited URL -- cannot resurrect it.
    """
    from ragstrike.dashboard.context import build_context

    context = build_context(
        services=None,  # type: ignore[arg-type]  - the palette decision never touches services
        state=AppState(raw={}),
        config=DashboardConfig(theme="light"),
        backend_online=False,
    )

    assert context.palette.name == "dark"


def test_the_configured_default_applies_when_nothing_was_chosen() -> None:
    from ragstrike.dashboard.context import build_context

    context = build_context(
        services=None,  # type: ignore[arg-type]
        state=AppState(raw={}),
        config=DashboardConfig(theme="dark"),
        backend_online=False,
    )

    assert context.palette.name == "dark"


def test_an_unknown_theme_name_falls_back_rather_than_raising() -> None:
    """A hand-edited URL or a stale preference must not be able to break the page."""
    assert palette_for("nonsense").name == "dark"


def test_both_palettes_produce_a_complete_stylesheet() -> None:
    """The 'half dark, half light' bug was the stylesheet not covering Streamlit's own chrome."""
    from ragstrike.dashboard.theme import stylesheet

    for name in ("dark", "light"):
        css = stylesheet(palette_for(name))
        # The native-widget variables are what make the toggle repaint Streamlit's own components.
        assert "--background-color" in css
        assert "stAppViewContainer" in css
        assert "rs-table" in css
