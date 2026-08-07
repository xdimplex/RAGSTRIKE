"""``ReportModel`` -- one fully-resolved, format-independent report.

**One model, N renderers.** Every computation happens here, once; a renderer only chooses how to
present what it is given. That is what guarantees the HTML, JSON, and Markdown outputs agree with
each other, and what makes adding a format a change that touches no arithmetic anywhere.

**Nothing here knows about HTML, Markdown, or a file path.** A section holds resolved values and
plain strings. If a renderer needs a number formatted differently, that is the renderer's decision
to make -- pushing it here would mean every other format inherits it.

The ten sections are the ones the Phase 11 brief enumerates, in report order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
import uuid


@dataclass(frozen=True, slots=True)
class CoverPage:
    """Section 1 -- who produced this, against what, and when."""

    project: str = "RAGStrike"
    title: str = "RAG Security Assessment"
    organization: str = ""
    framework_version: str = ""
    analyzer_version: str = ""
    report_version: str = "1.0.0"
    scan_id: str = ""
    target: str = ""
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    logo: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "title": self.title,
            "organization": self.organization,
            "framework_version": self.framework_version,
            "analyzer_version": self.analyzer_version,
            "report_version": self.report_version,
            "scan_id": self.scan_id,
            "target": self.target,
            "generated_at": self.generated_at.isoformat(),
            "logo": self.logo,
        }


@dataclass(frozen=True, slots=True)
class ExecutiveSummary:
    """Section 2 -- the whole scan in numbers a non-specialist can read.

    ``coverage`` is carried alongside the counts deliberately. A scan where six of ten plugins
    reached no verdict is a different statement from one where all ten did, and a summary showing
    only "no failures" cannot distinguish them.
    """

    status: str = "UNKNOWN"
    risk_score: float = 0.0
    confidence: float = 0.0
    confidence_band: str = "low"
    plugins_executed: int = 0
    passed: int = 0
    failed: int = 0
    inconclusive: int = 0
    errored: int = 0
    skipped: int = 0
    coverage: float = 0.0
    duration_ms: int = 0
    headline: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "risk_score": round(self.risk_score, 2),
            "confidence": round(self.confidence, 4),
            "confidence_band": self.confidence_band,
            "plugins_executed": self.plugins_executed,
            "passed": self.passed,
            "failed": self.failed,
            "inconclusive": self.inconclusive,
            "errored": self.errored,
            "skipped": self.skipped,
            "coverage": round(self.coverage, 4),
            "duration_ms": self.duration_ms,
            "headline": self.headline,
        }


@dataclass(frozen=True, slots=True)
class RiskBreakdown:
    """Section 3 -- findings per severity.

    Counts **failures only**. A PASS graded INFO is not an informational finding; it is the absence
    of a finding, and listing it here would inflate every report with rows that mean nothing.
    """

    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    informational: int = 0

    @property
    def total(self) -> int:
        return self.critical + self.high + self.medium + self.low + self.informational

    @property
    def actionable(self) -> int:
        """Findings above informational -- what a reader is expected to do something about."""
        return self.critical + self.high + self.medium + self.low

    def to_dict(self) -> dict[str, Any]:
        return {
            "critical": self.critical,
            "high": self.high,
            "medium": self.medium,
            "low": self.low,
            "informational": self.informational,
            "total": self.total,
            "actionable": self.actionable,
        }


@dataclass(frozen=True, slots=True)
class CategorySummary:
    """Section 4 -- one row per attack category."""

    category: str
    label: str = ""
    score: float = 0.0
    findings: int = 0
    passed: int = 0
    failed: int = 0
    confidence: float = 0.0
    worst_severity: str = "INFO"

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "label": self.label or self.category,
            "score": round(self.score, 2),
            "findings": self.findings,
            "passed": self.passed,
            "failed": self.failed,
            "confidence": round(self.confidence, 4),
            "worst_severity": self.worst_severity,
        }


@dataclass(frozen=True, slots=True)
class EvidenceBlock:
    """Section 6 material, carried inside its finding.

    Whatever redaction a pack applied is preserved exactly. The reporting engine never attempts to
    reverse it and never adds any of its own -- a pack that redacted did so for a reason it
    understands better than this layer does.
    """

    summary: str = ""
    text: str = ""
    sources: tuple[str, ...] = ()
    chunk_ids: tuple[str, ...] = ()
    signals: tuple[dict[str, Any], ...] = ()
    timing: dict[str, Any] = field(default_factory=dict)
    structured: dict[str, Any] = field(default_factory=dict)
    #: Reserved. Always empty today -- the field exists so a future screenshot has somewhere to
    #: arrive without a shape change.
    attachments: tuple[dict[str, Any], ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (self.text or self.sources or self.signals or self.structured)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "text": self.text,
            "sources": list(self.sources),
            "chunk_ids": list(self.chunk_ids),
            "signals": list(self.signals),
            "timing": self.timing,
            "structured": self.structured,
            "attachments": list(self.attachments),
        }


@dataclass(frozen=True, slots=True)
class FindingEntry:
    """Section 5 -- one finding, fully resolved for presentation."""

    finding_id: str
    plugin: str
    category: str
    severity: str
    status: str
    confidence: float
    confidence_band: str = "low"
    risk_score: float = 0.0
    description: str = ""
    observed: str = ""
    expected: str = ""
    evidence: EvidenceBlock = field(default_factory=EvidenceBlock)
    recommendation: str = ""
    remediation: str = ""
    references: tuple[str, ...] = ()
    execution_ms: int = 0
    notes: str = ""

    @property
    def is_vulnerability(self) -> bool:
        return self.status == "FAIL"

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "plugin": self.plugin,
            "category": self.category,
            "severity": self.severity,
            "status": self.status,
            "confidence": round(self.confidence, 4),
            "confidence_band": self.confidence_band,
            "risk_score": round(self.risk_score, 2),
            "description": self.description,
            "observed": self.observed,
            "expected": self.expected,
            "evidence": self.evidence.to_dict(),
            "recommendation": self.recommendation,
            "remediation": self.remediation,
            "references": list(self.references),
            "execution_ms": self.execution_ms,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class RecommendationGroup:
    """Section 7 -- advice grouped by the severity that prompted it."""

    severity: str
    items: tuple[dict[str, Any], ...] = ()

    @property
    def count(self) -> int:
        return len(self.items)

    def to_dict(self) -> dict[str, Any]:
        return {"severity": self.severity, "count": self.count, "items": list(self.items)}


@dataclass(frozen=True, slots=True)
class ScanStatistics:
    """Section 8 -- how the scan ran, as opposed to what it found."""

    duration_ms: int = 0
    plugin_count: int = 0
    finding_count: int = 0
    average_plugin_ms: float = 0.0
    slowest_plugin: str = ""
    slowest_plugin_ms: int = 0
    analyzer_version: str = ""
    framework_version: str = ""
    scoring_model_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "duration_ms": self.duration_ms,
            "plugin_count": self.plugin_count,
            "finding_count": self.finding_count,
            "average_plugin_ms": round(self.average_plugin_ms, 2),
            "slowest_plugin": self.slowest_plugin,
            "slowest_plugin_ms": self.slowest_plugin_ms,
            "analyzer_version": self.analyzer_version,
            "framework_version": self.framework_version,
            "scoring_model_version": self.scoring_model_version,
        }


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    """One moment in section 9."""

    kind: str
    label: str
    at: datetime
    detail: str = ""
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label,
            "at": self.at.isoformat(),
            "detail": self.detail,
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True, slots=True)
class ChartData:
    """Section 10 -- **data only, never an image.**

    A chart model is a series of labelled values a renderer or a dashboard turns into a picture.
    Producing images here would bind the reporting engine to a plotting library and make the JSON
    export carry megabytes of PNG nobody asked for.
    """

    chart_id: str
    title: str
    kind: str
    labels: tuple[str, ...] = ()
    values: tuple[float, ...] = ()
    series: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "chart_id": self.chart_id,
            "title": self.title,
            "kind": self.kind,
            "labels": list(self.labels),
            "values": list(self.values),
            "series": list(self.series),
        }


@dataclass(frozen=True, slots=True)
class ReportModel:
    """A complete report, resolved and format-independent."""

    report_id: str
    cover: CoverPage
    summary: ExecutiveSummary
    risk: RiskBreakdown
    categories: tuple[CategorySummary, ...] = ()
    findings: tuple[FindingEntry, ...] = ()
    recommendations: tuple[RecommendationGroup, ...] = ()
    statistics: ScanStatistics = field(default_factory=ScanStatistics)
    timeline: tuple[TimelineEvent, ...] = ()
    charts: tuple[ChartData, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex

    @property
    def vulnerabilities(self) -> list[FindingEntry]:
        """Findings asserting a weakness. ``INCONCLUSIVE`` is excluded -- an undetermined result is
        not evidence of weakness any more than of strength."""
        return [f for f in self.findings if f.is_vulnerability]

    @property
    def scan_id(self) -> str:
        return self.cover.scan_id

    def findings_by_severity(self) -> dict[str, list[FindingEntry]]:
        """Failures grouped by severity, worst first, so a renderer need not re-derive the order."""
        order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
        grouped: dict[str, list[FindingEntry]] = {level: [] for level in order}
        for finding in self.vulnerabilities:
            grouped.setdefault(finding.severity, []).append(finding)
        return {level: items for level, items in grouped.items() if items}

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "cover": self.cover.to_dict(),
            "executive_summary": self.summary.to_dict(),
            "risk_breakdown": self.risk.to_dict(),
            "category_summary": [c.to_dict() for c in self.categories],
            "findings": [f.to_dict() for f in self.findings],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "statistics": self.statistics.to_dict(),
            "timeline": [t.to_dict() for t in self.timeline],
            "charts": [c.to_dict() for c in self.charts],
            "metadata": self.metadata,
        }


__all__ = [
    "CategorySummary",
    "ChartData",
    "CoverPage",
    "EvidenceBlock",
    "ExecutiveSummary",
    "FindingEntry",
    "RecommendationGroup",
    "ReportModel",
    "RiskBreakdown",
    "ScanStatistics",
    "TimelineEvent",
]
