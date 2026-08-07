"""``ChartDataBuilder`` -- chart **data**, never images.

The brief is explicit and the reason is worth stating: producing images here would bind the
reporting engine to a plotting library, make the JSON export carry megabytes of PNG nobody asked
for, and force a headless rendering dependency on a tool that otherwise runs anywhere Python does.

A chart model is labelled values. An HTML renderer can draw them, a dashboard can plot them
interactively, and a JSON consumer can ignore them -- all from the same data.
"""

from __future__ import annotations

from ragstrike.analyzers.base.finding import Finding
from ragstrike.models.values.enums import PluginOutcome, Severity
from ragstrike.reporters.models.report import ChartData, TimelineEvent

#: Worst-first, so every severity chart reads the same way round regardless of what a scan found.
#: Fixed 2-point risk buckets. Fixed rather than computed so a histogram can be compared against
#: last month's report, which is most of what a risk chart is for.
_RISK_BUCKET_WIDTH = 2
_RISK_BUCKET_LABELS = ("0-2", "2-4", "4-6", "6-8", "8-10")

_SEVERITY_ORDER = (
    Severity.CRITICAL,
    Severity.HIGH,
    Severity.MEDIUM,
    Severity.LOW,
    Severity.INFO,
)


class ChartDataBuilder:
    """Builds the six chart models the brief names. Pure and stateless."""

    def build_all(
        self, findings: list[Finding], timeline: tuple[TimelineEvent, ...] = ()
    ) -> tuple[ChartData, ...]:
        return (
            self.severity_distribution(findings),
            self.category_distribution(findings),
            self.plugin_execution_time(findings),
            self.risk_score_distribution(findings),
            self.pass_vs_fail(findings),
            self.timeline_chart(timeline),
        )

    def severity_distribution(self, findings: list[Finding]) -> ChartData:
        """Failures per severity.

        Every severity appears, including zeros. Omitting empty ones would make two scans render
        with different axes, and a reader comparing them would have to notice that themselves.
        """
        failures = [f for f in findings if f.status is PluginOutcome.FAIL]
        counts = dict.fromkeys(_SEVERITY_ORDER, 0)
        for finding in failures:
            if finding.severity in counts:
                counts[finding.severity] += 1

        return ChartData(
            chart_id="severity_distribution",
            title="Findings by severity",
            kind="bar",
            labels=tuple(level.value for level in _SEVERITY_ORDER),
            values=tuple(float(counts[level]) for level in _SEVERITY_ORDER),
        )

    def category_distribution(self, findings: list[Finding]) -> ChartData:
        """Failures per category, in name order so the chart is stable between runs."""
        counts: dict[str, int] = {}
        for finding in findings:
            category = finding.category or "uncategorized"
            counts.setdefault(category, 0)
            if finding.status is PluginOutcome.FAIL:
                counts[category] += 1

        ordered = sorted(counts.items())
        return ChartData(
            chart_id="category_distribution",
            title="Findings by category",
            kind="bar",
            labels=tuple(name for name, _ in ordered),
            values=tuple(float(count) for _, count in ordered),
        )

    def plugin_execution_time(self, findings: list[Finding]) -> ChartData:
        """Milliseconds per plugin, slowest first -- the ordering a reader actually wants."""
        durations: dict[str, int] = {}
        for finding in findings:
            raw = finding.metadata.get("execution_ms", 0)
            try:
                durations[finding.plugin_id] = max(durations.get(finding.plugin_id, 0), int(raw))
            except (TypeError, ValueError):
                durations.setdefault(finding.plugin_id, 0)

        ordered = sorted(durations.items(), key=lambda item: (-item[1], item[0]))
        return ChartData(
            chart_id="plugin_execution_time",
            title="Execution time by plugin (ms)",
            kind="bar",
            labels=tuple(name for name, _ in ordered),
            values=tuple(float(ms) for _, ms in ordered),
        )

    def risk_score_distribution(self, findings: list[Finding]) -> ChartData:
        """Risk scores bucketed 0-2, 2-4, 4-6, 6-8, 8-10.

        Fixed buckets rather than computed ones: a histogram whose bins move with the data cannot
        be compared against last month's report, which is most of what a risk chart is for.
        """
        buckets = dict.fromkeys(_RISK_BUCKET_LABELS, 0)
        for finding in findings:
            if finding.status is not PluginOutcome.FAIL:
                continue
            index = min(int(finding.risk_score // _RISK_BUCKET_WIDTH), len(_RISK_BUCKET_LABELS) - 1)
            buckets[_RISK_BUCKET_LABELS[index]] += 1

        return ChartData(
            chart_id="risk_score_distribution",
            title="Risk score distribution",
            kind="histogram",
            labels=tuple(buckets),
            values=tuple(float(v) for v in buckets.values()),
        )

    def pass_vs_fail(self, findings: list[Finding]) -> ChartData:
        """Every outcome, including the undetermined ones.

        A pass/fail chart that hides INCONCLUSIVE would imply a scan reached a verdict everywhere,
        which is exactly the overstatement the whole outcome vocabulary exists to prevent.
        """
        counts = dict.fromkeys(PluginOutcome, 0)
        for finding in findings:
            counts[finding.status] += 1

        return ChartData(
            chart_id="pass_vs_fail",
            title="Outcomes",
            kind="pie",
            labels=tuple(outcome.value for outcome in PluginOutcome),
            values=tuple(float(counts[outcome]) for outcome in PluginOutcome),
        )

    def timeline_chart(self, timeline: tuple[TimelineEvent, ...]) -> ChartData:
        """Events as a series, for a Gantt-style or scatter rendering."""
        return ChartData(
            chart_id="timeline",
            title="Scan timeline",
            kind="timeline",
            labels=tuple(event.label for event in timeline),
            series=tuple(
                {
                    "label": event.label,
                    "kind": event.kind,
                    "at": event.at.isoformat(),
                    "duration_ms": event.duration_ms,
                }
                for event in timeline
            ),
        )


__all__ = ["ChartDataBuilder"]
