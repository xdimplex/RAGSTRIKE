"""UI component tests.

WHAT THESE ASSERT
    Components are pure functions returning HTML, so these tests check the markup directly rather
    than a screenshot. The interesting claims are not "it renders" -- they are:

    1. **Attacker-influenced text is escaped.** Payloads, target responses, plugin descriptions from
       third-party packs, and finding titles all flow into these components. A component that failed
       to escape would make the tool's own test corpus an XSS payload against its own dashboard.
    2. **Colour carries meaning correctly.** An operator reads colour before text. A MEDIUM rendered
       in the HIGH colour is a misreport, and an unknown severity rendered in red is manufactured
       alarm.
    3. **Nothing raises on missing data.** A dashboard is what you open *because* something is
       wrong, so every component has to survive partial input.
"""

from __future__ import annotations

import pytest

from ragstrike.dashboard.components.badges import (
    badge,
    grade_badge,
    grade_hero,
    outcome_badge,
    risk_badge,
    risk_band,
    severity_badge,
)
from ragstrike.dashboard.components.cards import (
    key_values,
    metric_card,
    plugin_card,
    report_card,
    status_card,
    summary_card,
    target_card,
)
from ragstrike.dashboard.components.controls import (
    FacetOptions,
    confirmation_prompt,
    facet_options,
)
from ragstrike.dashboard.components.feedback import (
    banner,
    empty_state,
    error_panel,
    loading_overlay,
    render_exception,
    toast,
)
from ragstrike.dashboard.components.html import escape, join, style, tag
from ragstrike.dashboard.components.log_viewer import log_viewer, visible_lines
from ragstrike.dashboard.components.progress import (
    format_duration,
    progress_bar,
    scan_progress,
    severity_bars,
)
from ragstrike.dashboard.components.timeline import TimelineEvent, timeline
from ragstrike.dashboard.services.errors import BackendUnavailableError, FriendlyError
from ragstrike.dashboard.services.models import (
    Authorization,
    LogLine,
    PluginView,
    ReportView,
    ScanProgress,
    TargetHealth,
    TargetView,
)
from ragstrike.dashboard.theme.palette import DARK, LIGHT

#: The classic reflected-XSS probe. Used verbatim by real prompt-injection payloads, which is
#: exactly why it has to be inert everywhere it lands.
XSS = '<script>alert("x")</script>'


# -- html primitives -------------------------------------------------------------------------------


def test_escape_neutralises_markup() -> None:
    assert "<script>" not in escape(XSS)
    assert "&lt;script&gt;" in escape(XSS)


def test_attribute_values_cannot_break_out_of_the_quote() -> None:
    """A colour arriving from configuration must not be able to close the attribute and open a new
    one -- that is an attribute-injection hole, not a styling bug."""
    markup = tag("div", "", style=style({"color": '" onload="alert(1)'}))

    assert 'onload="alert(1)"' not in markup
    assert "&quot;" in markup


def test_empty_attributes_are_dropped() -> None:
    assert tag("div", "x", class_="", title=None) == "<div>x</div>"


def test_underscores_become_hyphens_in_attribute_names() -> None:
    assert 'data-scan-id="s1"' in tag("div", "", data_scan_id="s1")


def test_join_drops_empty_fragments() -> None:
    assert join(["a", "", "b"]) == "ab"


# -- badges ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("severity", "attribute"),
    [
        ("CRITICAL", "critical"),
        ("HIGH", "high"),
        ("MEDIUM", "medium"),
        ("LOW", "low"),
        ("INFO", "informational"),
    ],
)
def test_every_severity_gets_its_own_colour(severity: str, attribute: str) -> None:
    """Two severities sharing a colour is a misreport an operator cannot see."""
    assert getattr(DARK, attribute) in severity_badge(DARK, severity)


def test_an_unknown_severity_is_not_painted_red() -> None:
    """An unrecognised value is *unknown*, not *severe*. Red would manufacture alarm from a version
    mismatch between the dashboard and the engine."""
    markup = severity_badge(DARK, "APOCALYPTIC")

    assert DARK.critical not in markup
    assert DARK.informational in markup


def test_severity_is_case_insensitive() -> None:
    assert severity_badge(DARK, "high") == severity_badge(DARK, "HIGH")


def test_inconclusive_is_a_warning_not_a_neutral() -> None:
    """ "We could not tell" needs attention. Greying it out is how it gets read as "fine"."""
    assert DARK.warn in outcome_badge(DARK, "INCONCLUSIVE")


@pytest.mark.parametrize(
    ("outcome", "attribute"),
    [("PASS", "ok"), ("FAIL", "danger"), ("ERROR", "critical"), ("SKIPPED", "neutral")],
)
def test_plugin_outcomes_map_onto_distinct_colours(outcome: str, attribute: str) -> None:
    assert getattr(DARK, attribute) in outcome_badge(DARK, outcome)


@pytest.mark.parametrize(
    ("score", "label"),
    [(95.0, "CRITICAL"), (75.0, "HIGH"), (50.0, "MEDIUM"), (20.0, "LOW"), (2.0, "MINIMAL")],
)
def test_risk_bands_follow_the_published_thresholds(score: float, label: str) -> None:
    assert risk_band(score)[0] == label


def test_a_risk_badge_states_the_score_as_well_as_the_band() -> None:
    """The band alone loses the difference between 70 and 89, which is the difference between
    "schedule this" and "stop the release"."""
    markup = risk_badge(DARK, 94.0)

    assert "94.0" in markup
    assert "CRITICAL" in markup


@pytest.mark.parametrize(("grade", "attribute"), [("A", "ok"), ("C", "warn"), ("F", "critical")])
def test_grades_are_coloured_by_band(grade: str, attribute: str) -> None:
    assert getattr(DARK, attribute) in grade_badge(DARK, grade)


def test_a_missing_grade_reads_as_ungraded_rather_than_as_an_a() -> None:
    assert "UNGRADED" in grade_badge(DARK, "")


def test_the_grade_hero_always_carries_its_coverage_qualifier() -> None:
    """ADR-020. A grade computed from half the intended cases is a different claim from one computed
    from all of them, and the letter alone invites being quoted as though it were the same."""
    assert "coverage 60%" in grade_hero(DARK, "F", coverage=0.6)


def test_a_badge_label_is_escaped() -> None:
    assert "<script>" not in badge(XSS, DARK.accent)


# -- cards -----------------------------------------------------------------------------------------


def test_key_values_omits_rows_with_no_value() -> None:
    """An empty row is a row an operator reads as "the system does not know", when the truth is
    "there is nothing to say"."""
    markup = key_values([("URL", "http://127.0.0.1:9000"), ("Scope", "")])

    assert "URL" in markup
    assert "Scope" not in markup


def test_an_unknown_subsystem_status_renders_as_unknown_not_healthy() -> None:
    markup = status_card(DARK, "ChromaDB", "who-knows")

    assert DARK.ok not in markup


def test_a_metric_delta_needs_a_colour_to_render() -> None:
    """Up is good for coverage and bad for risk. The component refuses to guess, so a caller that
    forgets to say which gets no colour rather than the wrong one."""
    assert "+4.0" not in metric_card("Risk", "94", delta="+4.0")
    assert "+4.0" in metric_card("Risk", "94", delta="+4.0", delta_colour=DARK.danger)


def test_a_refused_plugin_shows_why_it_was_refused() -> None:
    """ "Rejected" with no reason leaves an operator unable to tell a permission refusal from a
    version mismatch -- two problems with completely different fixes."""
    plugin = PluginView(
        slug="greedy-pack",
        status="rejected",
        rejection_reason="requests NETWORK_EGRESS; allow_elevated_permissions is false",
    )

    markup = plugin_card(DARK, plugin)

    assert "allow_elevated_permissions is false" in markup
    assert "REFUSED" in markup


def test_a_plugin_description_from_a_third_party_pack_is_escaped() -> None:
    """A pack manifest is data a third party wrote. It reaches this card unmodified."""
    markup = plugin_card(DARK, PluginView(slug="p", description=XSS))

    assert "<script>" not in markup


def test_a_target_without_authorization_says_so_on_its_face() -> None:
    """ADR-017. A target with no authorization record cannot be scanned, and the operator needs to
    see that before they try, not when the start button refuses."""
    markup = target_card(DARK, TargetView(id="t", name="t", url="http://127.0.0.1:9000"))

    assert "NO AUTHORIZATION" in markup


def test_an_authorized_local_target_is_marked_local_and_authorized() -> None:
    target = TargetView(
        id="vulnerable-rag",
        name="vulnerable-rag",
        url="http://127.0.0.1:9000",
        authorization=Authorization("local-operator", "LOCAL-LAB", "loopback only"),
        health=TargetHealth(reachable=True, latency_ms=12, checked_at="2026-07-30T12:00:00+00:00"),
    )

    markup = target_card(DARK, target)

    assert "LOCAL" in markup
    assert "AUTHORIZED" in markup
    assert "ONLINE" in markup


def test_a_non_local_target_is_flagged() -> None:
    markup = target_card(DARK, TargetView(id="x", name="x", url="https://example.com"))

    assert "NON-LOCAL" in markup


def test_an_unprobed_target_reads_as_unknown_rather_than_offline() -> None:
    """ "Not checked" and "checked and dead" call for different operator responses."""
    assert TargetHealth().status == "unknown"


def test_a_report_card_shows_size_in_units_a_human_reads() -> None:
    markup = report_card(DARK, ReportView(id="rep-1", size_bytes=13_402))

    assert "13.1 KB" in markup


def test_summary_card_escapes_its_values() -> None:
    assert "<script>" not in summary_card("t", {"Payload": XSS})


# -- progress --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, "0s"), (45, "45s"), (90, "1m 30s"), (3661, "1h 01m")],
)
def test_durations_are_formatted_the_way_a_human_reads_them(seconds: float, expected: str) -> None:
    assert format_duration(seconds) == expected


def test_a_negative_duration_does_not_render_as_negative_time() -> None:
    assert format_duration(-5) == "0s"


def test_a_progress_bar_clamps_rather_than_overflowing() -> None:
    """A backend reporting 7 of 5 cases should not paint outside the bar."""
    assert "width:100.0%" in progress_bar(1.4, DARK.accent)
    assert "width:0.0%" in progress_bar(-1.0, DARK.accent)


def test_progress_with_no_total_reads_as_zero_not_as_complete() -> None:
    """Division by zero has two wrong answers here; a full bar is the dangerous one."""
    assert ScanProgress(scan_id="s", total=0, completed=0).percent == 0.0


def test_a_finished_scan_reads_as_complete_even_without_counts() -> None:
    assert ScanProgress(scan_id="s", state="completed").percent == 1.0


def test_the_live_panel_labels_its_estimate_as_an_estimate() -> None:
    """A countdown that looks authoritative and is wrong by a factor of three is worse than one the
    operator knows to distrust."""
    markup = scan_progress(
        DARK,
        ScanProgress(scan_id="s", state="running", completed=40, total=100, eta_s=120.0),
    )

    assert "Est. remaining" in markup
    assert "2m 00s" in markup


def test_severity_bars_render_nothing_when_there_are_no_findings() -> None:
    assert severity_bars(DARK, {}) == ""
    assert severity_bars(DARK, {"HIGH": 0}) == ""


def test_severity_bars_scale_to_the_largest_count() -> None:
    markup = severity_bars(DARK, {"CRITICAL": 1, "HIGH": 4})

    assert "width:100.0%" in markup  # HIGH, the largest
    assert "width:25.0%" in markup  # CRITICAL, a quarter of it


# -- log viewer ------------------------------------------------------------------------------------


def test_a_log_line_containing_a_payload_is_inert() -> None:
    """Log lines contain target responses -- which is to say, whatever an injection payload said."""
    markup = log_viewer(DARK, [LogLine(message=XSS, level="INFO")])

    assert "<script>" not in markup


def test_log_filtering_keeps_levels_it_does_not_recognise() -> None:
    """Hiding an unrecognised level is how a new FATAL would go unnoticed."""
    lines = [LogLine(level="DEBUG", message="d"), LogLine(level="FATAL", message="f")]

    kept = {line.level for line in visible_lines(lines, "WARNING")}

    assert "FATAL" in kept
    assert "DEBUG" not in kept


def test_the_log_viewer_caps_what_it_lays_out() -> None:
    """A browser asked to lay out fifty thousand lines stops responding, at which point the operator
    can read none of them."""
    lines = [LogLine(message=f"line {i}") for i in range(500)]

    markup = log_viewer(DARK, lines, limit=10)

    assert "line 499" in markup
    assert "line 0<" not in markup


def test_an_empty_log_says_so_rather_than_rendering_an_empty_box() -> None:
    assert "No log output yet" in log_viewer(DARK, [])


# -- timeline and feedback -------------------------------------------------------------------------


def test_a_timeline_event_is_escaped_and_coloured_by_kind() -> None:
    markup = timeline(DARK, [TimelineEvent(title=XSS, kind="FAIL")])

    assert "<script>" not in markup
    assert DARK.danger in markup


def test_an_empty_timeline_renders_nothing() -> None:
    assert timeline(DARK, []) == ""


def test_an_empty_state_says_what_to_do_next() -> None:
    """An empty region with nothing in it is indistinguishable from a broken one."""
    markup = empty_state(
        "▤", "No reports yet", "Reports come from a completed scan.", hint="Try X."
    )

    assert "No reports yet" in markup
    assert "Try X." in markup


def test_a_toast_is_coloured_by_level() -> None:
    assert DARK.danger in toast(DARK, "error", "boom")
    assert DARK.ok in toast(DARK, "success", "done")


def test_the_loading_overlay_has_a_spinner_and_a_message() -> None:
    markup = loading_overlay("Generating report...")

    assert "rs-overlay__spinner" in markup
    assert "Generating report..." in markup


def test_an_error_panel_carries_its_remedy() -> None:
    """A failure with no next step is a dead end. Every error class ships one."""
    markup = error_panel(DARK, BackendUnavailableError("refused").friendly())

    assert "Backend offline" in markup
    assert "Start the RAGStrike API" in markup


def test_an_unexpected_exception_still_becomes_a_friendly_panel() -> None:
    """A Streamlit traceback takes the page down; this keeps the operator able to navigate away."""
    markup = render_exception(DARK, ValueError("weird"))

    assert "Unexpected error" in markup
    assert "ValueError" in markup


def test_a_friendly_error_without_a_remedy_still_renders() -> None:
    assert "Odd" in error_panel(DARK, FriendlyError(title="Odd", message="hm"))


def test_a_banner_is_escaped() -> None:
    assert "<script>" not in banner(DARK, "warning", XSS)


# -- controls (the pure half) ----------------------------------------------------------------------


def test_facet_options_come_from_the_rows_on_screen() -> None:
    """A filter offering a value no row has is a dead end the operator finds by clicking it."""
    rows = [
        PluginView(slug="a", category="evaluation"),
        PluginView(slug="b", category="evaluation"),
    ]

    options = facet_options(rows)

    assert options.categories == ("evaluation",)
    assert options.plugins == ("a", "b")


def test_facet_options_are_empty_for_an_empty_page() -> None:
    assert facet_options([]) == FacetOptions()


def test_a_confirmation_names_the_action_and_the_subject() -> None:
    """ "Are you sure?" is the dialog people click through."""
    prompt = confirmation_prompt("Delete", "rep-0004")

    assert "Delete" in prompt
    assert "rep-0004" in prompt
    assert "cannot be undone" in prompt


# -- the light theme renders too -------------------------------------------------------------------


def test_components_work_under_both_palettes() -> None:
    """A component that hardcoded a dark colour would pass every test above and be unreadable in
    light mode."""
    for palette in (DARK, LIGHT):
        assert palette.critical in severity_badge(palette, "CRITICAL")
        assert palette.ok in status_card(palette, "SQLite", "ok")
