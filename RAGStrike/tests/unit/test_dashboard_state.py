"""State tests.

THE CLAIM UNDER TEST: **state is centralized and not duplicated.**

Streamlit re-runs the whole script on every interaction, so anything that must survive a click lives
in ``st.session_state``. Left to itself that is a global dictionary with hand-typed string keys, and
the first typo is a silent no-op that looks like a bug in whatever read it.

These tests pin three things:

1. Every key the dashboard writes is in the closed :data:`STATE_KEYS` registry. A page inventing its
   own key is the failure the registry exists to prevent, and this is where it gets caught.
2. Reads survive a value of the wrong shape -- which is what a session that outlived a code change
   actually holds.
3. The queues that must drain, drain. A toast that re-renders on every re-run reads as the app being
   stuck.
"""

from __future__ import annotations

from ragstrike.dashboard.config import DashboardConfig, ReportPreferences
from ragstrike.dashboard.state.keys import STATE_KEYS, StateKey
from ragstrike.dashboard.state.store import AppState, Notification, ScanHandle


def state() -> AppState:
    """A state bound to a plain dict -- the seam that makes this whole layer testable."""
    return AppState(raw={})


# -- the key registry ------------------------------------------------------------------------------


def test_every_write_lands_on_a_registered_key() -> None:
    """The "do not duplicate state" rule, made checkable.

    Exercises every mutator on the class and then asserts that nothing outside the registry was
    written. A page that reached past AppState and set its own key would fail here.
    """
    app = state()

    app.current_page = "home"
    app.current_scan = ScanHandle(scan_id="s1")
    app.current_target = "vulnerable-rag"
    app.selected_report = "rep-1"
    app.loaded_plugins = ["prompt-injection"]
    app.settings = DashboardConfig()
    app.search_query = "prompt"
    app.notify("info", "hello")
    app.filters_for("reports")["state"] = object()
    app.request_confirmation("delete", "rep-1")
    app.advance_poll()
    _ = app.preferences

    assert set(app.raw) <= STATE_KEYS


def test_the_registry_covers_the_seven_the_brief_names() -> None:
    """Current Scan, Current Target, Loaded Plugins, Selected Report, Application Settings, User
    Preferences, Current Page."""
    required = {
        StateKey.CURRENT_SCAN,
        StateKey.CURRENT_TARGET,
        StateKey.LOADED_PLUGINS,
        StateKey.SELECTED_REPORT,
        StateKey.SETTINGS,
        StateKey.PREFERENCES,
        StateKey.CURRENT_PAGE,
    }

    assert {key.value for key in required} <= STATE_KEYS


def test_keys_are_namespaced() -> None:
    """Streamlit's session state is shared with widget keys. An unprefixed ``settings`` would
    collide with any widget a page named the same thing."""
    assert all(key.startswith("rs.") for key in STATE_KEYS)


def test_no_two_keys_share_a_value() -> None:
    assert len(STATE_KEYS) == len(list(StateKey))


# -- reads that survive a stale session ------------------------------------------------------------


def test_a_value_of_the_wrong_shape_falls_back_to_the_default() -> None:
    """A session that outlived a code change holds values in the previous shape. Falling back beats
    raising on the page the operator opened to diagnose something else."""
    app = state()
    app.raw[StateKey.CURRENT_PAGE.value] = 42

    assert app.current_page == ""


def test_a_stale_scan_handle_reads_as_no_scan() -> None:
    app = state()
    app.raw[StateKey.CURRENT_SCAN.value] = {"scan_id": "s1"}  # the old dict shape

    assert app.current_scan is None


def test_settings_load_from_the_environment_on_first_access() -> None:
    app = state()

    assert isinstance(app.settings, DashboardConfig)
    assert app.has(StateKey.SETTINGS)


def test_settings_are_not_reloaded_once_the_session_owns_them() -> None:
    """The settings page changes them without touching the process environment; a reload would
    silently undo that on the next re-run."""
    app = state()
    app.settings = DashboardConfig(theme="light")

    assert app.settings.theme == "light"


# -- the working set -------------------------------------------------------------------------------


def test_clearing_the_current_scan_removes_it_rather_than_storing_none() -> None:
    """A stored ``None`` and an absent key read the same but behave differently under ``has``."""
    app = state()
    app.current_scan = ScanHandle(scan_id="s1")
    app.current_scan = None

    assert not app.has(StateKey.CURRENT_SCAN)
    assert app.current_scan is None


def test_plugin_selection_is_deduplicated_and_order_preserving() -> None:
    """Order matters because it is what the operator sees in the multiselect; duplicates would
    schedule the same plugin twice."""
    app = state()
    app.loaded_plugins = ["b", "a", "b"]

    assert app.loaded_plugins == ["b", "a"]


def test_the_plugin_selection_is_separate_from_the_inventory() -> None:
    """Keeping them apart is what stops a stale selection resurrecting an uninstalled plugin."""
    assert StateKey.LOADED_PLUGINS is not StateKey.PLUGIN_CACHE


# -- queues ----------------------------------------------------------------------------------------


def test_notifications_drain_exactly_once() -> None:
    """With Streamlit's re-run model, a toast that is not drained repeats on every interaction."""
    app = state()
    app.notify("success", "scan started")

    assert len(app.drain_notifications()) == 1
    assert app.drain_notifications() == []


def test_notifications_preserve_the_order_they_were_raised_in() -> None:
    app = state()
    app.notify("info", "first")
    app.notify("error", "second")

    assert [n.message for n in app.drain_notifications()] == ["first", "second"]


def test_a_notification_carries_its_detail() -> None:
    app = state()
    app.notify("error", "validation failed", "manifest: missing version")

    assert app.drain_notifications()[0] == Notification(
        "error", "validation failed", "manifest: missing version"
    )


def test_a_corrupt_notification_queue_does_not_break_the_render() -> None:
    app = state()
    app.raw[StateKey.NOTIFICATIONS.value] = ["not a notification"]

    assert app.drain_notifications() == []


# -- confirmations ---------------------------------------------------------------------------------


def test_a_confirmation_must_be_requested_before_it_is_pending() -> None:
    """This is what makes a destructive action two clicks. Streamlit discards local variables
    between re-runs, so the pending flag has to live in state or "confirm delete" becomes
    "delete"."""
    app = state()

    assert app.pending_confirmation("delete") is None
    app.request_confirmation("delete", "rep-1")
    assert app.pending_confirmation("delete") == "rep-1"


def test_resolving_a_confirmation_clears_only_that_dialog() -> None:
    app = state()
    app.request_confirmation("delete-report", "rep-1")
    app.request_confirmation("delete-target", "t1")

    app.resolve_confirmation("delete-report")

    assert app.pending_confirmation("delete-report") is None
    assert app.pending_confirmation("delete-target") == "t1"


def test_resolving_an_unknown_dialog_is_harmless() -> None:
    state().resolve_confirmation("never-requested")


# -- filters ---------------------------------------------------------------------------------------


def test_each_page_gets_its_own_filter_namespace_inside_one_state_entry() -> None:
    """Per-page filters without per-page state keys: still exactly one filter state."""
    app = state()
    app.filters_for("reports")["text"] = "html"
    app.filters_for("plugins")["text"] = "injection"

    assert app.filters_for("reports")["text"] == "html"
    assert app.filters_for("plugins")["text"] == "injection"
    assert app.raw[StateKey.FILTERS.value].keys() == {"reports", "plugins"}


def test_a_corrupt_filter_store_is_replaced_rather_than_raising() -> None:
    app = state()
    app.raw[StateKey.FILTERS.value] = "not a dict"

    assert app.filters_for("reports") == {}


# -- polling ---------------------------------------------------------------------------------------


def test_the_poll_tick_is_monotonic() -> None:
    """Pages read it to know a refresh happened. A tick that went backwards would make a stale view
    look fresh."""
    app = state()

    assert [app.advance_poll(), app.advance_poll(), app.advance_poll()] == [1, 2, 3]


# -- configuration values --------------------------------------------------------------------------


def test_config_overrides_produce_a_new_object() -> None:
    """A configuration that mutates while Streamlit re-runs the script is the source of "it worked a
    second ago"."""
    original = DashboardConfig()

    updated = original.with_overrides(theme="light")

    assert original.theme == "dark"
    assert updated.theme == "light"


def test_report_preferences_are_a_value_too() -> None:
    config = DashboardConfig().with_overrides(reports=ReportPreferences(default_format="markdown"))

    assert config.reports.default_format == "markdown"


def test_demo_mode_is_readable_from_the_config() -> None:
    assert not DashboardConfig().is_demo
    assert DashboardConfig(transport="demo").is_demo
