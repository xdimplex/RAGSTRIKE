"""Filter and sort tests.

THE CLAIM UNDER TEST: **one filter implementation, applied to four different row types.**

The brief asks for filtering by severity, plugin, target, date, category, status, and risk score --
across findings, scans, reports, and plugins. Four implementations would be four chances for
"severity: HIGH" to mean something slightly different in one of them.

The subtle requirement is what happens to a facet that does not apply: filtering a *reports* list by
category must be a no-op, not an empty page. A filter that silently empties a page is how an
operator concludes there is no data when there is.
"""

from __future__ import annotations

import pytest

from ragstrike.dashboard.services.filters import (
    MAX_RISK,
    SEVERITY_ORDER,
    FilterState,
    apply_filters,
    matches,
    severity_rank,
    sort_items,
)
from ragstrike.dashboard.services.models import (
    FindingView,
    PluginView,
    ReportView,
    ScanView,
)


def finding(**kwargs: object) -> FindingView:
    defaults: dict[str, object] = {
        "id": "f1",
        "plugin": "prompt-injection",
        "category": "prompt_injection",
        "title": "System prompt overridden",
        "severity": "HIGH",
        "status": "FAIL",
        "risk_score": 76.0,
        "confidence": 0.9,
        "timestamp": "2026-07-30T12:00:00+00:00",
    }
    defaults.update(kwargs)
    return FindingView(**defaults)  # type: ignore[arg-type]  # keyword construction from a mapping


FINDINGS = [
    finding(id="f1", severity="CRITICAL", risk_score=94.0),
    finding(id="f2", severity="HIGH", risk_score=76.0, plugin="prompt-leakage"),
    finding(id="f3", severity="LOW", risk_score=12.0, status="PASS", category="evaluation"),
    finding(id="f4", severity="INFO", risk_score=2.0, status="INCONCLUSIVE"),
]


# -- the default filter ----------------------------------------------------------------------------


def test_an_untouched_filter_matches_everything() -> None:
    """An empty facet means "no constraint", not "match nothing". Anything else makes the page blank
    the moment a filter panel is opened."""
    assert apply_filters(FINDINGS, FilterState()) == FINDINGS


def test_an_untouched_filter_reports_itself_inactive() -> None:
    """Drives the "N filters active -- clear" affordance."""
    assert not FilterState().active
    assert FilterState(severities=("HIGH",)).active
    assert FilterState(max_risk=50.0).active


def test_clearing_returns_to_the_default() -> None:
    assert not FilterState(severities=("HIGH",), text="x").cleared().active


def test_a_filter_state_is_a_value() -> None:
    """The panel produces a new state on change, so a half-applied filter can never be observed
    partway through a render."""
    original = FilterState()

    updated = original.with_text("prompt")

    assert original.text == ""
    assert updated.text == "prompt"


# -- individual facets -----------------------------------------------------------------------------


def test_severity_filters_to_the_selected_levels() -> None:
    kept = apply_filters(FINDINGS, FilterState(severities=("CRITICAL", "HIGH")))

    assert [f.id for f in kept] == ["f1", "f2"]


def test_severity_matching_is_case_insensitive() -> None:
    assert apply_filters(FINDINGS, FilterState(severities=("critical",)))


def test_plugin_filtering_works_on_findings_and_on_plugin_rows() -> None:
    """A finding names its plugin ``plugin``; a plugin row names itself ``slug``. Both have to
    work or the same facet behaves differently on two pages."""
    assert len(apply_filters(FINDINGS, FilterState(plugins=("prompt-leakage",)))) == 1

    plugins = [PluginView(slug="prompt-injection"), PluginView(slug="prompt-leakage")]
    assert len(apply_filters(plugins, FilterState(plugins=("prompt-leakage",)))) == 1


def test_status_is_read_from_whichever_field_the_row_uses() -> None:
    """A finding has ``status``, a scan has ``state``, a completed scan also has ``outcome``."""
    assert len(apply_filters(FINDINGS, FilterState(statuses=("PASS",)))) == 1

    scans = [ScanView(id="s1", state="running"), ScanView(id="s2", state="completed")]
    assert len(apply_filters(scans, FilterState(statuses=("RUNNING",)))) == 1


def test_category_filters_findings() -> None:
    assert len(apply_filters(FINDINGS, FilterState(categories=("evaluation",)))) == 1


def test_target_filters_scans() -> None:
    scans = [ScanView(id="s1", target="vulnerable-rag"), ScanView(id="s2", target="secure-rag")]

    assert len(apply_filters(scans, FilterState(targets=("secure-rag",)))) == 1


def test_risk_range_is_inclusive_at_both_ends() -> None:
    kept = apply_filters(FINDINGS, FilterState(min_risk=12.0, max_risk=76.0))

    assert {f.id for f in kept} == {"f2", "f3"}


def test_the_full_risk_range_constrains_nothing() -> None:
    assert apply_filters(FINDINGS, FilterState(min_risk=0.0, max_risk=MAX_RISK)) == FINDINGS


def test_free_text_searches_the_fields_a_human_would_expect() -> None:
    assert len(apply_filters(FINDINGS, FilterState(text="overridden"))) == len(FINDINGS)
    assert len(apply_filters(FINDINGS, FilterState(text="prompt-leakage"))) == 1


def test_free_text_is_case_insensitive() -> None:
    assert apply_filters(FINDINGS, FilterState(text="PROMPT-LEAKAGE"))


def test_free_text_does_not_search_every_attribute() -> None:
    """Otherwise typing "html" matches a report because its id happens to contain the letters."""
    reports = [ReportView(id="rep-0001", fmt="html"), ReportView(id="rep-0002", fmt="json")]

    assert apply_filters(reports, FilterState(text="html")) == []


# -- dates -----------------------------------------------------------------------------------------


def test_a_date_window_filters_by_the_row_timestamp() -> None:
    rows = [
        finding(id="old", timestamp="2026-07-01T12:00:00+00:00"),
        finding(id="new", timestamp="2026-07-30T12:00:00+00:00"),
    ]

    kept = apply_filters(rows, FilterState(date_from="2026-07-15"))

    assert [f.id for f in kept] == ["new"]


def test_the_date_window_is_inclusive() -> None:
    rows = [finding(id="edge", timestamp="2026-07-30T23:59:00+00:00")]

    assert apply_filters(rows, FilterState(date_from="2026-07-30", date_to="2026-07-30"))


def test_a_row_with_no_timestamp_is_not_excluded_by_a_date_filter() -> None:
    """An undated row is not evidence of being outside the window."""
    assert apply_filters([finding(id="x", timestamp="")], FilterState(date_from="2026-07-15"))


def test_a_scan_is_dated_by_when_it_started() -> None:
    scans = [ScanView(id="s1", started_at="2026-07-30T08:00:00+00:00")]

    assert apply_filters(scans, FilterState(date_from="2026-07-30"))


def test_a_report_is_dated_by_when_it_was_generated() -> None:
    reports = [ReportView(id="r1", generated_at="2026-07-30T08:00:00+00:00")]

    assert apply_filters(reports, FilterState(date_from="2026-07-30"))


# -- facets that do not apply ----------------------------------------------------------------------


def test_a_facet_the_rows_do_not_have_is_a_no_op_not_an_empty_page() -> None:
    """A reports list has no ``category``. Filtering by one there should leave the page alone --
    an operator who sees it empty concludes there are no reports."""
    reports = [ReportView(id="rep-1"), ReportView(id="rep-2")]

    assert len(apply_filters(reports, FilterState(categories=("prompt_injection",)))) == 2


def test_a_risk_filter_does_not_empty_a_page_of_rows_with_no_risk_score() -> None:
    plugins = [PluginView(slug="a"), PluginView(slug="b")]

    assert len(apply_filters(plugins, FilterState(min_risk=50.0))) == 2


def test_facets_combine_as_and() -> None:
    kept = apply_filters(FINDINGS, FilterState(severities=("HIGH",), statuses=("FAIL",)))

    assert [f.id for f in kept] == ["f2"]


def test_filtering_preserves_order() -> None:
    """The backend already returns rows in a meaningful order. Re-ordering as a side effect of
    filtering would look like a bug in the backend."""
    kept = apply_filters(FINDINGS, FilterState(min_risk=0.0))

    assert [f.id for f in kept] == [f.id for f in FINDINGS]


def test_matches_and_apply_filters_agree() -> None:
    state = FilterState(severities=("HIGH",))

    assert apply_filters(FINDINGS, state) == [f for f in FINDINGS if matches(f, state)]


# -- sorting ---------------------------------------------------------------------------------------


def test_severity_ranks_worst_first() -> None:
    """Alphabetical order puts CRITICAL after both HIGH and INFO, which is exactly backwards."""
    ranks = [severity_rank(name) for name in SEVERITY_ORDER]

    assert ranks == sorted(ranks)
    assert severity_rank("CRITICAL") < severity_rank("INFO")


def test_an_unknown_severity_sorts_last_rather_than_first() -> None:
    """An unrecognised value should not push itself to the top of a triage queue."""
    assert severity_rank("APOCALYPTIC") > severity_rank("INFO")


def test_sorting_by_severity_descending_puts_the_worst_first() -> None:
    """ "Descending" means most severe first, which is an *ascending* sort on rank. Getting this
    backwards is invisible in code review and obvious on screen."""
    ordered = sort_items(FINDINGS, "severity", descending=True)

    assert [f.severity for f in ordered] == ["CRITICAL", "HIGH", "LOW", "INFO"]


def test_sorting_by_severity_ascending_puts_the_least_severe_first() -> None:
    ordered = sort_items(FINDINGS, "severity", descending=False)

    assert ordered[0].severity == "INFO"


def test_sorting_by_risk_descending_puts_the_highest_first() -> None:
    ordered = sort_items(FINDINGS, "risk", descending=True)

    assert [f.risk_score for f in ordered] == [94.0, 76.0, 12.0, 2.0]


def test_sorting_by_name_is_case_insensitive() -> None:
    reports = [ReportView(id="b"), ReportView(id="A")]

    assert [r.id for r in sort_items(reports, "name", descending=False)] == ["A", "b"]


def test_sorting_by_date_uses_whichever_timestamp_the_row_has() -> None:
    scans = [
        ScanView(id="early", started_at="2026-07-01T00:00:00+00:00"),
        ScanView(id="late", started_at="2026-07-30T00:00:00+00:00"),
    ]

    assert [s.id for s in sort_items(scans, "date", descending=True)] == ["late", "early"]


def test_an_unknown_sort_key_leaves_the_order_untouched() -> None:
    """The backend's order is meaningful. Silently re-sorting by a key that does not exist would
    look like a backend bug rather than a bad sort selector."""
    assert sort_items(FINDINGS, "phase-of-the-moon") == FINDINGS


@pytest.mark.parametrize("key", ["severity", "risk", "date", "name", "target", "confidence"])
def test_every_offered_sort_key_works_on_every_row_type(key: str) -> None:
    """A sort key that raises on one page is a page an operator cannot sort."""
    for rows in (FINDINGS, [ScanView(id="s")], [ReportView(id="r")], [PluginView(slug="p")]):
        assert sort_items(rows, key) is not None
