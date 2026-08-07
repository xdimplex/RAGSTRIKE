"""Builder, statistics, and timeline tests.

Every number a report shows is computed here, once. The properties worth pinning are the ones a
reader would rely on: that the summary and the findings list agree, that undetermined results are
never presented as clean, and that ordering is stable between two renders of the same scan.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ragstrike.analyzers.base.finding import Finding
from ragstrike.models.values.enums import PluginOutcome, Severity
from ragstrike.reporters.builders.report_builder import (
    ExecutiveSummaryBuilder,
    ReportBuilder,
    ReportContext,
)
from ragstrike.reporters.charts.chart_builder import ChartDataBuilder
from ragstrike.reporters.statistics.statistics_builder import StatisticsBuilder
from ragstrike.reporters.timeline.timeline_builder import TimelineBuilder

NOW = datetime(2026, 7, 30, 12, 0, 0, tzinfo=UTC)


def finding(**kwargs) -> Finding:
    defaults = {
        "id": Finding.new_id(),
        "scan_id": "s1",
        "plugin_id": "prompt-injection",
        "category": "prompt_injection",
        "status": PluginOutcome.FAIL,
        "severity": Severity.HIGH,
        "confidence": 0.9,
        "confidence_band": "high",
        "risk_score": 7.2,
        "timestamp": NOW,
        "analyzer_version": "1.0.0",
        "recommendation": "Separate instructions from data",
        "metadata": {
            "execution_ms": 120,
            "remediation": "Use role separation.",
            "effort": "MEDIUM",
        },
    }
    defaults.update(kwargs)
    return Finding(**defaults)


# -- executive summary ----------------------------------------------------------------------------


def test_one_failure_makes_a_scan_vulnerable() -> None:
    """One confirmed failure among ninety passes is still a vulnerable system."""
    summary = ExecutiveSummaryBuilder().build(
        [finding()] + [finding(status=PluginOutcome.PASS) for _ in range(90)]
    )

    assert summary.status == "VULNERABLE"


def test_undetermined_results_never_read_as_secure() -> None:
    """A run that established nothing must not present as a clean bill of health."""
    summary = ExecutiveSummaryBuilder().build(
        [finding(status=PluginOutcome.INCONCLUSIVE), finding(status=PluginOutcome.PASS)]
    )

    assert summary.status == "INCONCLUSIVE"


def test_all_passing_is_secure() -> None:
    summary = ExecutiveSummaryBuilder().build([finding(status=PluginOutcome.PASS)] * 3)

    assert summary.status == "SECURE"


def test_no_findings_is_no_data_not_secure() -> None:
    assert ExecutiveSummaryBuilder().build([]).status == "NO DATA"


def test_the_headline_names_the_coverage_gap() -> None:
    """ "No failures found" and "no failures found, but a third reached no verdict" call for
    different responses."""
    summary = ExecutiveSummaryBuilder().build(
        [finding(status=PluginOutcome.PASS), finding(status=PluginOutcome.INCONCLUSIVE)]
    )

    assert "no verdict" in summary.headline
    assert "incomplete" in summary.headline


def test_a_complete_clean_scan_says_so() -> None:
    summary = ExecutiveSummaryBuilder().build([finding(status=PluginOutcome.PASS)] * 3)

    assert "every check reached a verdict" in summary.headline


def test_coverage_counts_only_determinate_outcomes() -> None:
    summary = ExecutiveSummaryBuilder().build(
        [
            finding(status=PluginOutcome.PASS),
            finding(status=PluginOutcome.FAIL),
            finding(status=PluginOutcome.INCONCLUSIVE),
            finding(status=PluginOutcome.ERROR),
        ]
    )

    assert summary.coverage == 0.5


def test_summary_counts_cover_every_finding() -> None:
    findings = [
        finding(status=PluginOutcome.PASS),
        finding(status=PluginOutcome.FAIL),
        finding(status=PluginOutcome.INCONCLUSIVE),
        finding(status=PluginOutcome.ERROR),
        finding(status=PluginOutcome.SKIPPED),
    ]

    s = ExecutiveSummaryBuilder().build(findings)

    assert s.passed + s.failed + s.inconclusive + s.errored + s.skipped == len(findings)


def test_confidence_averages_only_the_failures() -> None:
    """A report's headline confidence is about the findings, not about the passes."""
    summary = ExecutiveSummaryBuilder().build(
        [
            finding(confidence=0.8),
            finding(confidence=0.4),
            finding(status=PluginOutcome.PASS, confidence=1.0),
        ]
    )

    assert summary.confidence == pytest.approx(0.6)


# -- risk breakdown -------------------------------------------------------------------------------


def test_risk_breakdown_counts_failures_only() -> None:
    """A PASS graded INFO is the absence of a finding, not an informational one."""
    model = ReportBuilder().build(
        [
            finding(severity=Severity.INFO, status=PluginOutcome.PASS),
            finding(severity=Severity.HIGH),
        ],
        ReportContext(scan_id="s1"),
    )

    assert model.risk.informational == 0
    assert model.risk.high == 1
    assert model.risk.total == 1


def test_actionable_excludes_informational() -> None:
    model = ReportBuilder().build(
        [finding(severity=Severity.INFO), finding(severity=Severity.LOW)],
        ReportContext(scan_id="s1"),
    )

    assert model.risk.total == 2
    assert model.risk.actionable == 1


# -- categories -------------------------------------------------------------------------------------


def test_categories_get_human_labels() -> None:
    model = ReportBuilder().build([finding()], ReportContext(scan_id="s1"))

    assert model.categories[0].label == "Prompt Manipulation"


def test_an_unknown_category_renders_under_its_own_name() -> None:
    """An unlabelled category is a cosmetic gap, never a missing section."""
    model = ReportBuilder().build([finding(category="brand_new_pack")], ReportContext(scan_id="s1"))

    assert model.categories[0].label == "brand_new_pack"


def test_a_finding_with_no_category_is_grouped_not_dropped() -> None:
    model = ReportBuilder().build([finding(category="")], ReportContext(scan_id="s1"))

    assert model.categories[0].category == "uncategorized"


# -- finding ordering ----------------------------------------------------------------------------------


def test_findings_are_ordered_worst_first() -> None:
    """A reader opens this section to see the worst thing first."""
    model = ReportBuilder().build(
        [
            finding(severity=Severity.LOW, risk_score=2.0),
            finding(severity=Severity.CRITICAL, risk_score=10.0),
            finding(severity=Severity.MEDIUM, risk_score=5.0),
        ],
        ReportContext(scan_id="s1"),
    )

    assert next(f.severity for f in model.findings) == "CRITICAL"


def test_failures_sort_above_passes() -> None:
    model = ReportBuilder().build(
        [
            finding(status=PluginOutcome.PASS, severity=Severity.CRITICAL),
            finding(severity=Severity.LOW),
        ],
        ReportContext(scan_id="s1"),
    )

    assert model.findings[0].status == "FAIL"


def test_ordering_is_stable_between_builds() -> None:
    """An unstable sort would reorder a report between two renders of the same scan."""
    findings = [finding(severity=Severity.HIGH) for _ in range(5)]
    builder = ReportBuilder()

    first = [f.finding_id for f in builder.build(findings, ReportContext()).findings]
    second = [f.finding_id for f in builder.build(findings, ReportContext()).findings]

    assert first == second


# -- recommendations ------------------------------------------------------------------------------------


def test_recommendations_are_grouped_by_severity() -> None:
    model = ReportBuilder().build(
        [finding(severity=Severity.CRITICAL), finding(severity=Severity.LOW)],
        ReportContext(scan_id="s1"),
    )

    assert [g.severity for g in model.recommendations] == ["CRITICAL", "LOW"]


def test_duplicate_advice_is_deduplicated_with_findings_attached() -> None:
    """Ten findings sharing one remediation should produce one instruction with ten findings
    attached, not ten copies of the same paragraph."""
    model = ReportBuilder().build(
        [finding(recommendation="Same advice") for _ in range(10)], ReportContext(scan_id="s1")
    )

    group = model.recommendations[0]
    assert len(group.items) == 1
    assert len(group.items[0]["findings"]) == 10


def test_passes_contribute_no_recommendations() -> None:
    model = ReportBuilder().build([finding(status=PluginOutcome.PASS)], ReportContext(scan_id="s1"))

    assert model.recommendations == ()


# -- statistics ------------------------------------------------------------------------------------------


def test_statistics_count_distinct_plugins() -> None:
    stats = StatisticsBuilder().build(
        [finding(plugin_id="a"), finding(plugin_id="a"), finding(plugin_id="b")]
    )

    assert stats.plugin_count == 2
    assert stats.finding_count == 3


def test_the_slowest_plugin_is_identified() -> None:
    stats = StatisticsBuilder().build(
        [
            finding(plugin_id="fast", metadata={"execution_ms": 10}),
            finding(plugin_id="slow", metadata={"execution_ms": 900}),
        ]
    )

    assert stats.slowest_plugin == "slow"
    assert stats.slowest_plugin_ms == 900


def test_a_missing_duration_does_not_break_statistics() -> None:
    """A finding that did not record a duration is still a finding."""
    stats = StatisticsBuilder().build([finding(metadata={})])

    assert stats.average_plugin_ms == 0.0


def test_a_non_numeric_duration_is_tolerated() -> None:
    stats = StatisticsBuilder().build([finding(metadata={"execution_ms": "quick"})])

    assert stats.duration_ms == 0


def test_an_explicit_duration_overrides_the_sum() -> None:
    stats = StatisticsBuilder().build([finding()], duration_ms=5000)

    assert stats.duration_ms == 5000


def test_statistics_on_no_findings_do_not_divide_by_zero() -> None:
    assert StatisticsBuilder().build([]).average_plugin_ms == 0.0


# -- timeline -----------------------------------------------------------------------------------------------


def test_the_timeline_is_chronological() -> None:
    events = TimelineBuilder().build(
        [finding(timestamp=NOW + timedelta(seconds=5)), finding(timestamp=NOW)],
        scan_started=NOW - timedelta(seconds=10),
        report_generated=NOW + timedelta(seconds=20),
    )

    assert [e.at for e in events] == sorted(e.at for e in events)


def test_a_missing_boundary_produces_no_event_rather_than_a_fabricated_one() -> None:
    """A timeline showing an invented "scan started" is worse than one admitting the gap."""
    events = TimelineBuilder().build([finding()], report_generated=NOW)

    assert not any(e.kind == "scan_started" for e in events)


def test_the_report_generation_event_is_always_present() -> None:
    events = TimelineBuilder().build([], report_generated=NOW)

    assert [e.kind for e in events] == ["report_generated"]


def test_timeline_ordering_is_stable_for_identical_timestamps() -> None:
    """Findings frequently share a timestamp; an unstable sort would reorder the timeline between
    renders."""
    builder = TimelineBuilder()
    findings = [finding(plugin_id=f"p{i}", timestamp=NOW) for i in range(5)]

    first = [e.label for e in builder.build(findings, report_generated=NOW)]
    second = [e.label for e in builder.build(findings, report_generated=NOW)]

    assert first == second


# -- charts ---------------------------------------------------------------------------------------------------


def test_every_severity_appears_even_at_zero() -> None:
    """Omitting empty severities would make two scans render with different axes."""
    chart = ChartDataBuilder().severity_distribution([finding(severity=Severity.HIGH)])

    assert chart.labels == ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
    assert len(chart.values) == 5


def test_pass_vs_fail_includes_undetermined_outcomes() -> None:
    """Hiding INCONCLUSIVE would imply a scan reached a verdict everywhere."""
    chart = ChartDataBuilder().pass_vs_fail([finding()])

    assert "INCONCLUSIVE" in chart.labels


def test_risk_buckets_are_fixed_not_computed() -> None:
    """A histogram whose bins move with the data cannot be compared against last month's report."""
    builder = ChartDataBuilder()

    small = builder.risk_score_distribution([finding(risk_score=1.0)])
    large = builder.risk_score_distribution([finding(risk_score=9.5)])

    assert small.labels == large.labels


def test_execution_time_is_ordered_slowest_first() -> None:
    chart = ChartDataBuilder().plugin_execution_time(
        [
            finding(plugin_id="fast", metadata={"execution_ms": 5}),
            finding(plugin_id="slow", metadata={"execution_ms": 500}),
        ]
    )

    assert chart.labels[0] == "slow"


def test_all_six_charts_are_produced() -> None:
    charts = ChartDataBuilder().build_all([finding()])

    assert {c.chart_id for c in charts} == {
        "severity_distribution",
        "category_distribution",
        "plugin_execution_time",
        "risk_score_distribution",
        "pass_vs_fail",
        "timeline",
    }


def test_charts_contain_data_never_images() -> None:
    """The brief is explicit, and so is the implementation: labelled values only."""
    for chart in ChartDataBuilder().build_all([finding()]):
        assert isinstance(chart.labels, tuple)
        assert isinstance(chart.values, tuple)
        assert not hasattr(chart, "image")
