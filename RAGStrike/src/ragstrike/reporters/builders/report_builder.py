"""``ReportBuilder`` and ``ExecutiveSummaryBuilder`` -- turning findings into a report model.

**Every computation happens here, once.** Renderers present; they never calculate. That is what
guarantees the HTML, JSON, and Markdown outputs agree, and it means a change to how risk is
summarized takes effect in all three formats at once.

**The builder consumes findings, not plugins.** It imports `ragstrike.analyzers`, never a pack --
the reporting engine has no idea which plugins exist, and a pack shipped next year renders on the
day it ships.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ragstrike.analyzers.base.finding import Finding
from ragstrike.models.values.enums import PluginOutcome, Severity
from ragstrike.reporters.charts.chart_builder import ChartDataBuilder
from ragstrike.reporters.models.report import (
    CategorySummary,
    CoverPage,
    EvidenceBlock,
    ExecutiveSummary,
    FindingEntry,
    RecommendationGroup,
    ReportModel,
    RiskBreakdown,
)
from ragstrike.reporters.statistics.statistics_builder import StatisticsBuilder
from ragstrike.reporters.timeline.timeline_builder import TimelineBuilder

#: Human labels for the categories shipped so far. A category absent here renders under its own
#: name -- an unlabelled category is a cosmetic gap, never a missing section.
_CATEGORY_LABELS = {
    "prompt_injection": "Prompt Manipulation",
    "prompt_leakage": "Prompt Leakage",
    "context_poisoning": "Context Poisoning",
    "evaluation": "Security Evaluations",
}

_SEVERITY_ORDER = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")

#: Band thresholds, matching the analyzer's so a report never disagrees with the finding it renders.
_HIGH_CONFIDENCE = 0.75
_MEDIUM_CONFIDENCE = 0.4


@dataclass(frozen=True, slots=True)
class ReportContext:
    """Everything the builder needs that is not a finding.

    Grouped into one object so adding a field later does not change the builder's signature and
    every caller with it.
    """

    scan_id: str = ""
    target: str = ""
    title: str = "RAG Security Assessment"
    organization: str = ""
    framework_version: str = ""
    analyzer_version: str = ""
    report_version: str = "1.0.0"
    scoring_model_version: str = ""
    logo: str = ""
    duration_ms: int = 0
    scan_started: datetime | None = None
    scan_finished: datetime | None = None
    analysis_started: datetime | None = None
    analysis_finished: datetime | None = None
    generated_at: datetime | None = None
    scan_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class ExecutiveSummaryBuilder:
    """Builds the executive summary. Pure and stateless."""

    def build(
        self, findings: list[Finding], *, scan_score: float = 0.0, duration_ms: int = 0
    ) -> ExecutiveSummary:
        counts = dict.fromkeys(PluginOutcome, 0)
        for finding in findings:
            counts[finding.status] += 1

        determinate = counts[PluginOutcome.PASS] + counts[PluginOutcome.FAIL]
        coverage = determinate / len(findings) if findings else 0.0
        confidences = [f.confidence for f in findings if f.status is PluginOutcome.FAIL]
        confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return ExecutiveSummary(
            status=self._status(counts),
            risk_score=scan_score,
            confidence=confidence,
            confidence_band=self._band(confidence),
            plugins_executed=len({f.plugin_id for f in findings}),
            passed=counts[PluginOutcome.PASS],
            failed=counts[PluginOutcome.FAIL],
            inconclusive=counts[PluginOutcome.INCONCLUSIVE],
            errored=counts[PluginOutcome.ERROR],
            skipped=counts[PluginOutcome.SKIPPED],
            coverage=coverage,
            duration_ms=duration_ms,
            headline=self._headline(counts, coverage),
        )

    @staticmethod
    def _status(counts: dict[PluginOutcome, int]) -> str:
        """The scan's one-word verdict.

        ``VULNERABLE`` outranks everything: one confirmed failure among ninety passes is still a
        vulnerable system. ``INCONCLUSIVE`` outranks ``SECURE`` for the same reason it does at every
        other layer -- a run that established nothing must not read as a clean bill of health.
        """
        if counts[PluginOutcome.FAIL]:
            return "VULNERABLE"
        if counts[PluginOutcome.ERROR]:
            return "ERRORED"
        if counts[PluginOutcome.INCONCLUSIVE]:
            return "INCONCLUSIVE"
        if counts[PluginOutcome.PASS]:
            return "SECURE"
        return "NO DATA"

    @staticmethod
    def _band(confidence: float) -> str:
        if confidence >= _HIGH_CONFIDENCE:
            return "high"
        if confidence >= _MEDIUM_CONFIDENCE:
            return "medium"
        return "low"

    @staticmethod
    def _headline(counts: dict[PluginOutcome, int], coverage: float) -> str:
        """One sentence a non-specialist can act on.

        Names the coverage gap explicitly when there is one, because "no failures found" and "no
        failures found, but a third of checks reached no verdict" call for different responses.
        """
        failed = counts[PluginOutcome.FAIL]
        undetermined = counts[PluginOutcome.INCONCLUSIVE] + counts[PluginOutcome.ERROR]

        if failed:
            sentence = f"{failed} confirmed finding{'s' if failed != 1 else ''}."
        elif undetermined:
            sentence = "No confirmed findings."
        else:
            sentence = "No findings; every check reached a verdict."

        if undetermined:
            sentence += (
                f" {undetermined} check{'s' if undetermined != 1 else ''} reached no verdict "
                f"({coverage:.0%} coverage) -- treat this as an incomplete assessment."
            )
        return sentence


class ReportBuilder:
    """Assembles a complete :class:`ReportModel`."""

    def __init__(
        self,
        *,
        summary: ExecutiveSummaryBuilder | None = None,
        statistics: StatisticsBuilder | None = None,
        timeline: TimelineBuilder | None = None,
        charts: ChartDataBuilder | None = None,
    ) -> None:
        self.summary = summary or ExecutiveSummaryBuilder()
        self.statistics = statistics or StatisticsBuilder()
        self.timeline = timeline or TimelineBuilder()
        self.charts = charts or ChartDataBuilder()

    def build(self, findings: list[Finding], context: ReportContext) -> ReportModel:
        """Build every section, in report order."""
        generated_at = context.generated_at or datetime.now(UTC)

        # Inferred from the findings when the caller did not supply it. A report that cannot name
        # the analyzer version is untraceable to the rules that graded it, and expecting every
        # caller to copy the value across by hand is how it ends up empty -- which is exactly what
        # happened before an integration test caught it.
        analyzer_version = context.analyzer_version or next(
            (f.analyzer_version for f in findings if f.analyzer_version), ""
        )
        scan_id = context.scan_id or next((f.scan_id for f in findings if f.scan_id), "")

        timeline = self.timeline.build(
            findings,
            scan_started=context.scan_started,
            scan_finished=context.scan_finished,
            analysis_started=context.analysis_started,
            analysis_finished=context.analysis_finished,
            report_generated=generated_at,
        )

        return ReportModel(
            report_id=ReportModel.new_id(),
            cover=CoverPage(
                title=context.title,
                organization=context.organization,
                framework_version=context.framework_version,
                analyzer_version=analyzer_version,
                report_version=context.report_version,
                scan_id=scan_id,
                target=context.target,
                generated_at=generated_at,
                logo=context.logo,
            ),
            summary=self.summary.build(
                findings, scan_score=context.scan_score, duration_ms=context.duration_ms
            ),
            risk=self._risk_breakdown(findings),
            categories=self._categories(findings),
            findings=tuple(self._entry(f) for f in self._ordered(findings)),
            recommendations=self._recommendations(findings),
            statistics=self.statistics.build(
                findings,
                duration_ms=context.duration_ms,
                framework_version=context.framework_version,
                analyzer_version=analyzer_version,
                scoring_model_version=context.scoring_model_version,
            ),
            timeline=timeline,
            charts=self.charts.build_all(findings, timeline),
            metadata=dict(context.metadata),
        )

    # -- sections --------------------------------------------------------------------------------

    @staticmethod
    def _risk_breakdown(findings: list[Finding]) -> RiskBreakdown:
        """Counts **failures only** -- a PASS graded INFO is the absence of a finding, not an
        informational one."""
        counts = dict.fromkeys(_SEVERITY_ORDER, 0)
        for finding in findings:
            if finding.status is PluginOutcome.FAIL:
                counts[finding.severity.value] = counts.get(finding.severity.value, 0) + 1

        return RiskBreakdown(
            critical=counts["CRITICAL"],
            high=counts["HIGH"],
            medium=counts["MEDIUM"],
            low=counts["LOW"],
            informational=counts["INFO"],
        )

    @staticmethod
    def _categories(findings: list[Finding]) -> tuple[CategorySummary, ...]:
        grouped: dict[str, list[Finding]] = {}
        for finding in findings:
            grouped.setdefault(finding.category or "uncategorized", []).append(finding)

        summaries: list[CategorySummary] = []
        for category, group in sorted(grouped.items()):
            failures = [f for f in group if f.status is PluginOutcome.FAIL]
            confidences = [f.confidence for f in failures] or [f.confidence for f in group]
            worst = max(
                (f.severity for f in failures),
                key=lambda s: (
                    _SEVERITY_ORDER.index(s.value)
                    if s.value in _SEVERITY_ORDER
                    else len(_SEVERITY_ORDER)
                ),
                default=Severity.INFO,
            )
            summaries.append(
                CategorySummary(
                    category=category,
                    label=_CATEGORY_LABELS.get(category, category),
                    score=max((f.risk_score for f in failures), default=0.0),
                    findings=len(group),
                    passed=sum(1 for f in group if f.status is PluginOutcome.PASS),
                    failed=len(failures),
                    confidence=sum(confidences) / len(confidences) if confidences else 0.0,
                    worst_severity=worst.value,
                )
            )
        return tuple(summaries)

    @staticmethod
    def _ordered(findings: list[Finding]) -> list[Finding]:
        """Worst first, then by risk, then by plugin.

        A reader opens the detailed findings section to see the worst thing first; sorting by
        anything else makes them scroll to find it.
        """

        def key(finding: Finding) -> tuple[int, float, str]:
            severity_rank = (
                _SEVERITY_ORDER.index(finding.severity.value)
                if finding.severity.value in _SEVERITY_ORDER
                else len(_SEVERITY_ORDER)
            )
            status_rank = 0 if finding.status is PluginOutcome.FAIL else 1
            return (status_rank * 100 + severity_rank, -finding.risk_score, finding.plugin_id)

        return sorted(findings, key=key)

    @staticmethod
    def _entry(finding: Finding) -> FindingEntry:
        evidence = finding.evidence if isinstance(finding.evidence, dict) else {}
        return FindingEntry(
            finding_id=finding.id,
            plugin=finding.plugin_id,
            category=finding.category,
            severity=finding.severity.value,
            status=finding.status.value,
            confidence=finding.confidence,
            confidence_band=finding.confidence_band,
            risk_score=finding.risk_score,
            description=str(evidence.get("summary", "")),
            observed=str(evidence.get("text", "")),
            expected=str((evidence.get("structured") or {}).get("expected_summary", "")),
            evidence=EvidenceBlock(
                summary=str(evidence.get("summary", "")),
                text=str(evidence.get("text", "")),
                sources=tuple(str(s) for s in evidence.get("sources") or ()),
                chunk_ids=tuple(str(c) for c in evidence.get("chunk_ids") or ()),
                signals=tuple(s for s in evidence.get("signals") or () if isinstance(s, dict)),
                timing=dict(evidence.get("timing") or {}),
                structured=dict(evidence.get("structured") or {}),
            ),
            recommendation=finding.recommendation,
            remediation=str(finding.metadata.get("remediation", "")),
            references=finding.references,
            execution_ms=int(finding.metadata.get("execution_ms", 0) or 0),
            notes=finding.notes,
        )

    @staticmethod
    def _recommendations(findings: list[Finding]) -> tuple[RecommendationGroup, ...]:
        """Advice grouped by the severity that prompted it, worst first.

        Deduplicated by title within a group: ten findings sharing one remediation should produce
        one instruction with ten findings attached, not ten copies of the same paragraph.
        """
        grouped: dict[str, dict[str, dict[str, Any]]] = {level: {} for level in _SEVERITY_ORDER}

        for finding in findings:
            if finding.status is not PluginOutcome.FAIL or not finding.recommendation:
                continue
            bucket = grouped.setdefault(finding.severity.value, {})
            entry = bucket.setdefault(
                finding.recommendation,
                {
                    "title": finding.recommendation,
                    "remediation": str(finding.metadata.get("remediation", "")),
                    "effort": str(finding.metadata.get("effort", "")),
                    "references": list(finding.references),
                    "findings": [],
                },
            )
            entry["findings"].append(finding.id)

        return tuple(
            RecommendationGroup(severity=level, items=tuple(grouped[level].values()))
            for level in _SEVERITY_ORDER
            if grouped.get(level)
        )


__all__ = ["ExecutiveSummaryBuilder", "ReportBuilder", "ReportContext"]
