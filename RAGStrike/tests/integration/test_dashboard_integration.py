"""Dashboard integration tests -- the real Streamlit runtime, through ``AppTest``.

WHAT MAKES THESE DIFFERENT FROM THE UNIT SUITES
    The unit tests prove the pieces are right. These prove the *app* runs: the script executes top to
    bottom in Streamlit's own runtime, the router imports and calls real page modules, widgets are
    created, and session state survives a re-run. That is the layer where "every page renders" stops
    being an assumption.

WHY THE DEMO TRANSPORT
    A dashboard is a pure client of an API that this phase does not implement. The demo transport
    supplies deterministic responses over exactly the same service interfaces, so these tests cover
    the interesting states -- populated, empty, offline -- without a server. They cover the *UI*;
    nothing here asserts anything about the engine.

WHAT IS DELIBERATELY NOT TESTED HERE
    The live-scan poll loop. It sleeps for the configured interval and re-runs, by design, and
    driving that through AppTest would test the sleep. Its decision logic -- when to keep polling
    and when to stop -- is covered exhaustively in the service tests.
"""

from __future__ import annotations

from collections.abc import Iterator
import os
from pathlib import Path
from typing import Any

import pytest

#: Absolute, and deliberately so. ``AppTest.from_file`` resolves a RELATIVE path against the
#: directory of the file that calls it -- not against the working directory -- so the old relative
#: spelling resolved to ``tests/integration/src/ragstrike/dashboard/app.py`` and every test in this
#: module died with FileNotFoundError. Anchoring to the repo root makes the suite independent of
#: both the caller's location and the directory pytest happens to be invoked from.
APP = str(Path(__file__).resolve().parents[2] / "src" / "ragstrike" / "dashboard" / "app.py")

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _demo_transport() -> Iterator[None]:
    """Every test in this module runs against the demo transport unless it says otherwise."""
    previous = os.environ.get("RAGSTRIKE_DASHBOARD__TRANSPORT")
    os.environ["RAGSTRIKE_DASHBOARD__TRANSPORT"] = "demo"
    yield
    if previous is None:
        os.environ.pop("RAGSTRIKE_DASHBOARD__TRANSPORT", None)
    else:
        os.environ["RAGSTRIKE_DASHBOARD__TRANSPORT"] = previous


def run(page: str = "home", **session: Any) -> Any:
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(APP, default_timeout=120)
    app.session_state["rs.current_page"] = page
    for key, value in session.items():
        app.session_state[key] = value
    return app.run()


def markup(app: Any) -> str:
    """Everything the app wrote as markdown, concatenated. The components render into this."""
    return "\n".join(str(block.value) for block in app.markdown)


def body(app: Any) -> str:
    """Markdown plus captions and alerts -- what an operator actually reads."""
    parts = [markup(app)]
    for collection in ("caption", "info", "warning", "success", "error"):
        elements = getattr(app, collection, [])
        parts.extend(str(element.value) for element in elements)
    return "\n".join(parts)


# -- every page renders ----------------------------------------------------------------------------


PAGES = [
    "home",
    "scan_center",
    "targets",
    "plugins",
    "reports",
    "scan_history",
    "settings",
    "system_status",
    "about",
]


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_without_raising(page: str) -> None:
    """The claim the whole phase rests on. A page that throws takes the sidebar with it, leaving the
    operator unable to navigate away -- which is why ``app.py`` wraps the body in an error boundary,
    and why this test asserts the boundary never had to fire."""
    app = run(page)

    assert not app.exception, [str(e.value) for e in app.exception]


@pytest.mark.parametrize("page", PAGES)
def test_every_page_writes_a_header(page: str) -> None:
    app = run(page)

    assert "rs-header__title" in markup(app)


def test_the_stylesheet_is_written_before_anything_else() -> None:
    """Anything rendered before it appears unstyled for a frame."""
    app = run("home")

    assert str(app.markdown[0].value).startswith("<style>")


# -- the two load-bearing banners ------------------------------------------------------------------


def test_demo_mode_announces_itself_on_every_page() -> None:
    """Sample findings in a security tool are dangerous the moment they are mistaken for real ones.
    A screenshot of this screen has to carry the disclaimer."""
    for page in PAGES:
        assert "DEMO MODE" in markup(run(page)), f"{page} did not carry the demo banner"


def test_there_is_no_configuration_that_hides_the_demo_banner() -> None:
    """The banner is derived from the transport, not from a setting -- so it cannot be switched off
    while the data stays fake."""
    app = run("home", **{"rs.preferences": {"hide_banners": True}})

    assert "DEMO MODE" in markup(app)


def test_an_offline_backend_produces_one_clear_banner_not_nine_failures() -> None:
    """The whole reason the shell probes once and passes the answer down."""
    os.environ["RAGSTRIKE_DASHBOARD__TRANSPORT"] = "http"
    os.environ["RAGSTRIKE_DASHBOARD__API_BASE_URL"] = "http://127.0.0.1:1/api/v1"
    os.environ["RAGSTRIKE_DASHBOARD__REQUEST_TIMEOUT_S"] = "1"
    try:
        app = run("home")

        assert not app.exception, [str(e.value) for e in app.exception]
        assert "BACKEND OFFLINE" in markup(app)
    finally:
        os.environ.pop("RAGSTRIKE_DASHBOARD__API_BASE_URL", None)
        os.environ.pop("RAGSTRIKE_DASHBOARD__REQUEST_TIMEOUT_S", None)


def test_offline_pages_that_need_a_backend_say_so_rather_than_erroring() -> None:
    os.environ["RAGSTRIKE_DASHBOARD__TRANSPORT"] = "http"
    os.environ["RAGSTRIKE_DASHBOARD__API_BASE_URL"] = "http://127.0.0.1:1/api/v1"
    os.environ["RAGSTRIKE_DASHBOARD__REQUEST_TIMEOUT_S"] = "1"
    try:
        for page in ("targets", "plugins", "reports", "scan_history", "scan_center"):
            app = run(page)
            assert not app.exception, f"{page}: {[str(e.value) for e in app.exception]}"
            assert "rs-empty" in markup(app), f"{page} showed no empty state"
    finally:
        os.environ.pop("RAGSTRIKE_DASHBOARD__API_BASE_URL", None)
        os.environ.pop("RAGSTRIKE_DASHBOARD__REQUEST_TIMEOUT_S", None)


# -- navigation ------------------------------------------------------------------------------------


def test_the_sidebar_offers_every_registered_page() -> None:
    from ragstrike.dashboard.navigation.routes import ROUTES

    app = run("home")
    keys = {button.key for button in app.button}

    for route in ROUTES:
        assert f"rs.nav.{route.id}" in keys, f"{route.id} is missing from the sidebar"


def test_clicking_a_sidebar_entry_changes_page() -> None:
    app = run("home")

    app.button(key="rs.nav.plugins").click().run()

    assert app.session_state["rs.current_page"] == "plugins"
    assert "Plugins" in markup(app)


def test_a_quick_action_navigates() -> None:
    """Home's shortcuts read from the same registry as the sidebar."""
    app = run("home")

    app.button(key="rs.home.targets").click().run()

    assert app.session_state["rs.current_page"] == "targets"


def test_the_current_page_survives_a_re_run() -> None:
    """Streamlit discards everything not in session state on every interaction."""
    app = run("reports")

    app.run()

    assert app.session_state["rs.current_page"] == "reports"


def test_an_unknown_stored_page_lands_on_home_rather_than_crashing() -> None:
    """A session left over from a version with different pages."""
    app = run("a-page-that-was-removed")

    assert not app.exception
    assert "Dashboard" in markup(app)


# -- global search ---------------------------------------------------------------------------------


def test_the_sidebar_search_finds_a_plugin_and_offers_it_as_a_destination() -> None:
    app = run("home")

    app.text_input(key="rs.sidebar.search").set_value("prompt-injection").run()

    assert any(button.key == "rs.hit.plugin.prompt-injection" for button in app.button)


def test_clicking_a_search_hit_navigates_to_the_right_page() -> None:
    app = run("home")
    app.text_input(key="rs.sidebar.search").set_value("secure-rag").run()

    app.button(key="rs.hit.target.secure-rag").click().run()

    assert app.session_state["rs.current_page"] == "targets"
    assert app.session_state["rs.current_target"] == "secure-rag"


def test_a_search_with_no_matches_says_so() -> None:
    app = run("home")

    app.text_input(key="rs.sidebar.search").set_value("zzzzzzzz").run()

    assert "No matches" in body(app)


# -- home ------------------------------------------------------------------------------------------


def test_home_shows_the_nine_facts_the_brief_names() -> None:
    app = run("home")
    rendered = markup(app)

    for label in (
        "Framework version",
        "Status",
        "Targets",
        "Plugins",
        "Completed scans",
        "Last scan",
    ):
        assert label in rendered, f"Home is missing {label}"


def test_home_shows_recent_activity_and_a_latest_result() -> None:
    rendered = markup(run("home"))

    assert "rs-timeline" in rendered
    assert "rs-grade" in rendered


# -- targets ---------------------------------------------------------------------------------------


def test_the_targets_page_shows_configured_targets_with_their_authorization() -> None:
    rendered = markup(run("targets"))

    assert "vulnerable-rag" in rendered
    assert "AUTHORIZED" in rendered
    assert "LOCAL" in rendered


def test_the_targets_page_offers_only_the_operations_the_api_supports() -> None:
    """Verify and Select, and deliberately NOT Add, Edit, or Delete.

    This test previously required all four operations the original brief named, and passed while
    three of them were broken: the API answers 501 for create, update, and delete, so every click
    produced "request rejected". A target carries an authorization record naming who approved
    testing it, and one created over an unauthenticated local HTTP call would be self-issued -- so
    the backend refuses on purpose (ADR-017) and `configs/targets.yaml` is the only way in.

    The page now says that instead of offering buttons that cannot work, and this asserts the
    absence as firmly as the presence: a dead control is worse than a missing one, because it reads
    as a broken product rather than a deliberate boundary.
    """
    app = run("targets")
    keys = {button.key for button in app.button}

    assert "rs.tgt.verify.vulnerable-rag" in keys
    assert any("rs.tgt.select" in key for key in keys)
    assert not any("rs.tgt.delete" in key for key in keys)
    assert not any("rs.tgt.add" in key for key in keys)


def test_the_targets_page_explains_how_to_add_one() -> None:
    """Removing the form is only correct if the page says what to do instead."""
    text = body(run("targets"))

    assert "configs/targets.yaml" in text
    assert "authorization" in text.lower()


def test_the_add_form_states_the_local_only_default_before_it_is_submitted() -> None:
    """The dashboard does not enforce scope -- the engine does -- but it says plainly that the
    backend will refuse.

    Stated as a caption rather than a live validation message because Streamlit forms do not re-run
    on input change: a conditional warning would only appear *after* the operator had submitted the
    non-local URL, which is the wrong side of the mistake.
    """
    assert "Local targets only by default" in body(run("targets"))


# -- plugins ---------------------------------------------------------------------------------------


def test_the_plugins_page_lists_the_installed_inventory() -> None:
    app = run("plugins")
    rendered = markup(app)

    assert "Prompt Injection" in rendered
    # Tables render as fixed HTML rather than `st.dataframe`. See `widgets/tables.py`: the
    # interactive grid was column-resizable, ignored the theme, and needed pandas to draw text.
    assert "rs-table" in rendered


def test_the_plugins_page_offers_the_four_operations_the_brief_names() -> None:
    app = run("plugins")
    keys = {button.key for button in app.button}

    assert "rs.plugins.reload" in keys
    assert "rs.plg.off.prompt-injection" in keys
    assert "rs.plg.val.prompt-injection" in keys


def test_disabling_a_plugin_reports_it_and_flips_the_control() -> None:
    """A round trip through a real mutation: click, service call, toast, re-render."""
    app = run("plugins")

    app.button(key="rs.plg.off.prompt-injection").click().run()

    assert not app.exception
    assert any(button.key == "rs.plg.on.prompt-injection" for button in app.button)


def test_validating_a_plugin_reports_the_outcome() -> None:
    app = run("plugins")

    app.button(key="rs.plg.val.prompt-injection").click().run()

    assert not app.exception
    assert "validation rule" in markup(app)


def test_the_plugins_page_has_no_way_to_edit_plugin_code() -> None:
    """ "Do not edit plugin code." There is no editor, and no service method that would accept one."""
    from ragstrike.dashboard.services.plugin_service import PluginService

    assert not any(name in dir(PluginService) for name in ("edit", "write", "save", "update_code"))


# -- reports ---------------------------------------------------------------------------------------


def test_the_reports_page_lists_generated_reports() -> None:
    app = run("reports")

    assert "rs-table" in markup(app)
    assert "rep-0004" in markup(app)


def test_the_reports_page_offers_search_sort_and_filter() -> None:
    app = run("reports")

    assert any(widget.key == "rs.rep.search" for widget in app.text_input)
    assert any(widget.key == "rs.rep.sort" for widget in app.selectbox)
    assert any(widget.key == "rs.rep.desc" for widget in app.checkbox)


def test_searching_reports_narrows_the_list() -> None:
    app = run("reports")

    app.text_input(key="rs.rep.search").set_value("secure-rag").run()

    assert "rep-0002" in markup(app)
    assert "rep-0004" not in markup(app)


def test_a_search_matching_no_report_shows_an_empty_state_not_a_blank_page() -> None:
    app = run("reports")

    app.text_input(key="rs.rep.search").set_value("zzzzzz").run()

    assert "No reports match" in markup(app)


def test_pdf_is_offered_but_marked_unavailable() -> None:
    """A missing option looks like a bug; a disabled one that says why is information."""
    app = run("reports")
    formats = [widget for widget in app.selectbox if str(widget.key).startswith("rs.rep.fmt")]

    assert formats, "no export format selector"
    labels = [str(option) for option in formats[0].options]
    assert any("PDF" in label and "not available" in label for label in labels), labels
    assert any(label == "HTML" for label in labels)


def test_deleting_a_report_takes_two_clicks() -> None:
    app = run("reports")

    app.button(key="rs.rep.delete.rep-0004.request").click().run()

    assert "cannot be undone" in body(app)


# -- scan history ----------------------------------------------------------------------------------


def test_the_history_page_shows_every_column_the_brief_names() -> None:
    """Columns are asserted in the rendered header now that tables are fixed HTML.

    They used to be read off a pandas DataFrame. The table is hand-rolled HTML so that columns
    cannot be dragged, the palette applies, and drawing a dozen rows of strings does not need
    pandas -- so the assertion moves to the markup, which is what an operator actually sees.
    """
    rendered = markup(run("scan_history"))

    for column in ("Target", "Duration", "Plugins", "Result", "Risk", "Started"):
        assert f">{column}</th>" in rendered, f"{column} column missing from the history table"


def test_the_history_page_offers_details_replay_and_report_generation() -> None:
    app = run("scan_history")
    keys = {button.key for button in app.button}

    assert any("rs.hist.replay" in key for key in keys)
    assert any("rs.hist.gen" in key for key in keys)


def test_comparison_is_offered_once_there_are_two_finished_scans() -> None:
    app = run("scan_history")

    assert any(button.key == "rs.hist.compare" for button in app.button)


def test_comparing_two_scans_reports_new_fixed_and_persisting() -> None:
    app = run("scan_history")

    app.button(key="rs.hist.compare").click().run()

    rendered = markup(app)
    assert "New findings" in rendered
    assert "Fixed" in rendered
    assert "Persisting" in rendered


def test_replay_does_not_start_a_scan_by_itself() -> None:
    """A previous authorization confirmation was given for a scan that already finished. Replay
    prepares the plan and sends the operator back to confirm."""
    app = run("scan_history")

    app.button(key="rs.hist.replay.scan-0006").click().run()

    assert app.session_state["rs.current_page"] == "scan_center"
    assert "rs.current_scan" not in app.session_state


# -- scan center -----------------------------------------------------------------------------------


def test_start_scan_is_disabled_until_authorization_is_confirmed() -> None:
    """ADR-017, at the UI layer. The backend enforces the target's own authorization record
    independently; this is the deliberate redundancy in front of it."""
    app = run("scan_center")

    start = app.button(key="rs.scan.start")

    assert start.disabled


def test_confirming_authorization_enables_start_scan() -> None:
    app = run("scan_center")

    app.checkbox(key="rs.scan.authorized").check().run()

    assert not app.button(key="rs.scan.start").disabled


def test_the_scan_center_offers_target_profile_and_plugin_selection() -> None:
    app = run("scan_center")
    keys = {widget.key for widget in app.selectbox} | {widget.key for widget in app.multiselect}

    assert "rs.scan.target" in keys
    assert "rs.scan.categories" in keys
    assert "rs.scan.plugins" in keys
    assert any(widget.key == "rs.scan.profile" for widget in app.radio)
    assert any(widget.key == "rs.scan.name" for widget in app.text_input)


def test_the_plan_summary_labels_its_numbers_as_estimates() -> None:
    rendered = body(run("scan_center"))

    assert "Estimated" in rendered
    assert "Estimates, not predictions" in rendered


def test_a_running_scan_shows_progress_stage_plugin_and_logs() -> None:
    """The live view, rendered once rather than polled -- the poll loop's decision logic is covered
    in the service tests."""
    from ragstrike.dashboard.state.store import ScanHandle

    app = run("scan_center", **{"rs.current_scan": ScanHandle(scan_id="scan-0006", target="x")})
    rendered = markup(app)

    assert "rs-bar" in rendered
    assert "Stage" in rendered or "State" in rendered
    assert "rs-log" in rendered


# -- settings --------------------------------------------------------------------------------------


def test_settings_offers_every_preference_the_brief_names() -> None:
    app = run("settings")
    keys = {widget.key for widget in app.selectbox}
    keys |= {widget.key for widget in app.text_input}
    keys |= {widget.key for widget in app.number_input}

    for name in (
        "theme",
        "language",
        "log_level",
        "default_timeout_s",
        "default_target",
        "refresh_interval_s",
        "plugin_refresh_interval_s",
    ):
        assert f"rs.set.{name}" in keys, f"Settings is missing {name}"


def test_changing_the_theme_takes_effect_in_the_same_session() -> None:
    """The whole theme system, end to end: pick light, and the stylesheet that gets written is the
    light one."""
    from ragstrike.dashboard.theme.palette import LIGHT

    app = run("settings")

    app.selectbox(key="rs.set.theme").set_value("light").run()
    app.button(key="rs.set.apply").click().run()

    assert app.session_state["rs.settings"].theme == "light"
    assert LIGHT.background in str(app.markdown[0].value)


def test_settings_shows_the_effective_configuration_read_only() -> None:
    app = run("settings")

    assert app.json
    assert "Read-only" in body(app)


def test_settings_never_renders_a_credential() -> None:
    """ "Do not expose sensitive configuration." Redaction is by key name, so a field the backend
    starts sending tomorrow is covered today."""
    rendered = "\n".join(
        [body(run("settings")), *(str(block.value) for block in run("settings").json)]
    )

    for marker in ("api_key", "password", "secret", "token"):
        assert f'"{marker}"' not in rendered or "••••" in rendered


def test_the_language_selector_is_honest_about_being_a_placeholder() -> None:
    app = run("settings")

    assert app.selectbox(key="rs.set.language").options == ["en"]


# -- system status ---------------------------------------------------------------------------------


def test_system_status_shows_all_eight_subsystems() -> None:
    rendered = markup(run("system_status"))

    for name in (
        "FastAPI",
        "Ollama",
        "SQLite",
        "ChromaDB",
        "Analyzer",
        "Reporting Engine",
        "Plugin Framework",
        "SDK",
    ):
        assert name in rendered, f"System Status is missing {name}"


def test_system_status_shows_host_resources_and_uptime() -> None:
    rendered = markup(run("system_status"))

    assert "CPU" in rendered
    assert "Memory" in rendered
    assert "Uptime" in rendered


def test_a_degraded_subsystem_is_reported_as_degraded() -> None:
    """The fixture's reporting engine reports the PDF placeholder. Worst-wins has to surface it."""
    app = run("system_status")

    assert "degraded" in body(app).lower()


# -- about -----------------------------------------------------------------------------------------


def test_about_states_the_limits_as_well_as_the_claims() -> None:
    """A security tool whose limitations live only in its documentation gets quoted by its
    dashboard."""
    rendered = body(run("about"))

    assert "not a guarantee" in rendered.lower()
    assert "out of scope" in rendered.lower() or "Detection evasion" in rendered


# -- the error boundary ----------------------------------------------------------------------------


def test_a_page_that_raises_is_contained_rather_than_taking_the_app_down() -> None:
    """Without the boundary, an exception in one page kills the whole script -- sidebar included --
    and the operator cannot navigate away from the broken page."""
    from ragstrike.dashboard.context import PageContext
    from ragstrike.dashboard.layouts.page_layout import error_boundary
    from ragstrike.dashboard.services import build_services_with
    from ragstrike.dashboard.services.demo import DemoTransport
    from ragstrike.dashboard.state.store import AppState

    written: list[str] = []
    context = PageContext(
        services=build_services_with(DemoTransport()),
        state=AppState(raw={}),
        config=__import__(
            "ragstrike.dashboard.config", fromlist=["DashboardConfig"]
        ).DashboardConfig(),
    )

    import ragstrike.dashboard.layouts.page_layout as layout

    original = layout._write
    layout._write = written.append  # type: ignore[assignment]  # narrow, restored below
    try:
        with error_boundary(context):
            raise RuntimeError("the reports page exploded")
    finally:
        layout._write = original  # type: ignore[assignment]

    assert written
    assert "Unexpected error" in written[0]
    assert "the reports page exploded" in written[0]
