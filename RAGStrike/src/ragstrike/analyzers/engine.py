"""``AnalyzerEngine`` -- the orchestrator, and ``StandardAnalyzer`` -- the one that ships.

The pipeline, in order:

    validate -> normalize evidence -> apply rules -> confidence -> risk score -> recommend -> Finding

Each step is a separate engine with a single responsibility, so re-tuning scoring cannot break
evidence handling and a new rule type touches only the rule engine.

**No plugin is named anywhere in this module.** The engine reads ``Observation``, which is derived
from a domain entity, so a pack written next year is analyzable the day it ships.

**Nothing here touches the database.** Analysis is a pure transformation; persistence is a port the
caller supplies. That is what allows the whole engine to be tested without a database, and what the
layer contract enforces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import logging
from typing import Any

from ragstrike.analyzers.base.analyzer import BaseAnalyzer
from ragstrike.analyzers.base.finding import Finding
from ragstrike.analyzers.base.observation import Observation
from ragstrike.analyzers.confidence.confidence_engine import ConfidenceEngine
from ragstrike.analyzers.evidence.evidence_engine import EvidenceEngine
from ragstrike.analyzers.recommendations.recommendation_engine import RecommendationEngine
from ragstrike.analyzers.registry.analyzer_registry import AnalyzerRegistry
from ragstrike.analyzers.rules.rule_engine import RuleEngine
from ragstrike.analyzers.scoring.score_engine import ScanScore, ScoreEngine
from ragstrike.analyzers.validators.validation_engine import ValidationEngine, ValidationReport
from ragstrike.models.values.enums import PluginOutcome

log = logging.getLogger(__name__)

#: Bumped when the analysis pipeline changes in a way that alters findings. Travels onto every
#: finding, because a finding is only interpretable against the logic that produced it.
ANALYZER_VERSION = "1.0.0"


class StandardAnalyzer(BaseAnalyzer):
    """The general-purpose analyzer. Handles every category.

    It exists because every plugin already produces the same ``PluginResult`` shape, so one analyzer
    driven by configurable rules covers all of them. A specialised analyzer is only warranted when a
    category needs reasoning the rules cannot express -- and then it registers alongside this one
    rather than replacing it.
    """

    name = "standard"
    handles = ()
    version = ANALYZER_VERSION

    def __init__(
        self,
        *,
        rules: RuleEngine | None = None,
        evidence: EvidenceEngine | None = None,
        confidence: ConfidenceEngine | None = None,
        scores: ScoreEngine | None = None,
        recommendations: RecommendationEngine | None = None,
    ) -> None:
        self.rules = rules or RuleEngine()
        self.evidence = evidence or EvidenceEngine()
        self.confidence = confidence or ConfidenceEngine()
        self.scores = scores or ScoreEngine()
        self.recommendations = recommendations or RecommendationEngine()

    def analyze(self, observation: Observation) -> Finding:
        """Turn one observation into one finding. Pure."""
        evidence = self.evidence.normalize(observation)
        verdict = self.rules.evaluate(observation)
        confidence = self.confidence.compute(
            observation, evidence, modifier=verdict.confidence_modifier
        )
        risk = self.scores.score_finding(verdict.severity, confidence.score, verdict.status)
        advice = self.recommendations.recommend(
            plugin_id=observation.plugin_id,
            category=observation.category,
            severity=verdict.severity,
            plugin_supplied=str(observation.metadata.get("recommendation", "")),
        )

        return Finding(
            id=Finding.new_id(),
            scan_id=observation.scan_id,
            plugin_id=observation.plugin_id,
            category=observation.category,
            status=verdict.status,
            severity=verdict.severity,
            confidence=confidence.score,
            confidence_band=confidence.band,
            risk_score=risk,
            evidence=evidence.to_dict(),
            recommendation=advice.title,
            references=advice.references,
            timestamp=datetime.now(UTC),
            notes=verdict.notes,
            analyzer_version=self.version,
            metadata={
                "plugin_reported_status": observation.reported_status.value,
                "overrode_plugin": verdict.overrode_plugin,
                "matched_rules": list(verdict.matched),
                "confidence_components": confidence.components,
                "recommendation_scope": advice.scope,
                "remediation": advice.remediation,
                "effort": advice.effort,
                "execution_ms": observation.execution_ms,
                "target": observation.target,
            },
        )


@dataclass(frozen=True, slots=True)
class AnalysisReport:
    """Everything one analysis run produced.

    **The interface the future Reporting Engine consumes.** Structured objects only -- no HTML, no
    PDF, no formatting decisions. A renderer reads this; it does not reach back into the analyzer.
    """

    scan_id: str
    findings: tuple[Finding, ...] = ()
    score: ScanScore | None = None
    rejected: tuple[dict[str, Any], ...] = ()
    analyzer_version: str = ANALYZER_VERSION
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def vulnerabilities(self) -> list[Finding]:
        """Findings asserting a weakness. ``INCONCLUSIVE`` is excluded deliberately -- see
        :attr:`Finding.is_vulnerability`."""
        return [f for f in self.findings if f.is_vulnerability]

    @property
    def coverage(self) -> float:
        """Fraction of findings that actually settled the question.

        A scan of ten plugins where six were inconclusive is a different statement from one where
        all ten reached a verdict, and a report that shows only "no failures" cannot distinguish
        them.
        """
        if not self.findings:
            return 0.0
        return sum(1 for f in self.findings if f.is_determinate) / len(self.findings)

    def by_category(self) -> dict[str, list[Finding]]:
        grouped: dict[str, list[Finding]] = {}
        for finding in self.findings:
            grouped.setdefault(finding.category or "uncategorized", []).append(finding)
        return grouped

    def to_dict(self) -> dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "analyzer_version": self.analyzer_version,
            "generated_at": self.generated_at.isoformat(),
            "coverage": round(self.coverage, 4),
            "score": self.score.to_dict() if self.score else None,
            "findings": [f.to_dict() for f in self.findings],
            "rejected": list(self.rejected),
        }


class AnalyzerEngine:
    """Runs observations through the pipeline and produces an :class:`AnalysisReport`."""

    def __init__(
        self,
        *,
        registry: AnalyzerRegistry | None = None,
        validator: ValidationEngine | None = None,
        scores: ScoreEngine | None = None,
        default_analyzer: BaseAnalyzer | None = None,
    ) -> None:
        self.registry = registry or AnalyzerRegistry()
        self.validator = validator or ValidationEngine()
        self.scores = scores or ScoreEngine()
        self._default = default_analyzer or StandardAnalyzer()
        if not self.registry.names():
            # An empty registry would mean no analyzer for any category and therefore no findings
            # at all -- a silent, total failure. Seeding the shipped analyzer makes the engine
            # useful with no configuration.
            self.registry.register(self._default)

    def analyze_one(self, observation: Observation) -> Finding | None:
        """Analyze a single observation, or ``None`` if it fails validation."""
        report = self.validator.validate(observation)
        if not report.valid:
            log.warning(
                "observation rejected",
                extra={
                    "plugin_id": observation.plugin_id,
                    "errors": [str(e) for e in report.errors],
                },
            )
            return None
        return self._resolve(observation.category).analyze(observation)

    def analyze(self, observations: list[Observation], *, scan_id: str = "") -> AnalysisReport:
        """Analyze every observation and aggregate the result.

        Rejected observations are reported rather than dropped: a scan that silently analyzed eight
        of ten plugins produces output indistinguishable from one that analyzed all ten.
        """
        accepted, rejected = self.validator.validate_all(observations)

        findings = [self._resolve(o.category).analyze(o) for o in accepted]
        resolved_scan_id = scan_id or (observations[0].scan_id if observations else "")

        if rejected:
            log.warning("observations rejected", extra={"count": len(rejected)})

        return AnalysisReport(
            scan_id=resolved_scan_id,
            findings=tuple(findings),
            score=self.scores.score_scan(findings),
            rejected=tuple(
                {"observation": o.to_dict(), "validation": r.to_dict()} for o, r in rejected
            ),
            analyzer_version=ANALYZER_VERSION,
        )

    async def analyze_and_store(
        self,
        observations: list[Observation],
        repository: Any,
        *,
        scan_id: str = "",
    ) -> AnalysisReport:
        """Analyze, then persist through *repository*.

        *repository* is typed loosely on purpose: it is a
        :class:`~ragstrike.analyzers.base.ports.FindingRepository`, but naming that type here would
        not change what is accepted at runtime and the protocol is the documented contract. The
        engine cannot import a concrete repository -- ``database`` sits above ``analyzers`` in the
        layer contract, and this direction is what keeps analysis testable without one.
        """
        report = self.analyze(observations, scan_id=scan_id)
        if report.findings:
            await repository.add_findings(list(report.findings))
        return report

    def _resolve(self, category: str) -> BaseAnalyzer:
        """The analyzer for *category*, falling back to the shipped one.

        The fallback matters: a category with no registered specialist must still produce a
        finding, or installing a new pack would silently reduce coverage.
        """
        return self.registry.for_category(category) or self._default


def validation_summary(report: ValidationReport) -> str:
    """One-line rendering of a validation report, for logs and rejection records."""
    if report.valid:
        return "valid"
    return "; ".join(str(error) for error in report.errors)


def outcome_counts(findings: list[Finding]) -> dict[str, int]:
    """Findings per status. Every ``PluginOutcome`` appears, including zeros.

    Missing keys would force every consumer to write ``.get(status, 0)``, and one that forgets shows
    a blank where a zero belongs.
    """
    counts = {outcome.value: 0 for outcome in PluginOutcome}
    for finding in findings:
        counts[finding.status.value] += 1
    return counts


__all__ = [
    "ANALYZER_VERSION",
    "AnalysisReport",
    "AnalyzerEngine",
    "StandardAnalyzer",
    "outcome_counts",
    "validation_summary",
]
