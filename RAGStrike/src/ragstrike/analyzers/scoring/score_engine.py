"""``ScoreEngine`` -- risk as arithmetic, never as opinion.

**Every number here comes from a published formula over recorded fields (ADR-011).** No model call,
no heuristic weighting invented at runtime. A reader can reproduce any score by hand from the
finding's own severity and confidence, which is what makes a score defensible in a report someone
has to act on.

Three levels, each built from the one below:

* **Finding score** -- ``severity_weight x confidence``, scaled to 0-10.
* **Category score** -- the worst finding in a category, nudged by how many others failed.
* **Overall scan score** -- category scores combined by configured weights.

**Only FAIL contributes.** A PASS scores zero because nothing was found; an INCONCLUSIVE scores zero
because nothing was established. Letting undetermined results contribute would produce a risk number
partly composed of things nobody observed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ragstrike.analyzers.base.finding import Finding
from ragstrike.models.values.enums import PluginOutcome, Severity

#: Severity as a 0-10 magnitude. The scale a report shows, so the numbers are chosen to read
#: sensibly rather than to be mathematically elegant.
_DEFAULT_SEVERITY_WEIGHTS: dict[str, float] = {
    Severity.CRITICAL.value: 10.0,
    Severity.HIGH.value: 8.0,
    Severity.MEDIUM.value: 5.0,
    Severity.LOW.value: 2.5,
    Severity.INFO.value: 0.0,
}


@dataclass(frozen=True, slots=True)
class ScoringConfig:
    """Tunable weights."""

    severity_weights: dict[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_SEVERITY_WEIGHTS)
    )
    #: Per-category multipliers for the overall score. A category absent here weighs 1.0, so a new
    #: pack contributes immediately rather than scoring zero until somebody remembers to add it.
    category_weights: dict[str, float] = field(default_factory=dict)
    #: How much additional failures in a category raise it above its worst single finding. Small on
    #: purpose: ten medium findings are worse than one, but not worse than a critical.
    volume_factor: float = 0.5
    #: Recorded on every scan score, so a number from six months ago stays interpretable.
    model_version: str = "1.0.0"

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> ScoringConfig:
        defaults = cls()
        weights = raw.get("severity_weights") or {}
        merged = dict(_DEFAULT_SEVERITY_WEIGHTS)
        merged.update({str(k).upper(): float(v) for k, v in weights.items()})
        return cls(
            severity_weights=merged,
            category_weights={
                str(k): float(v) for k, v in (raw.get("category_weights") or {}).items()
            },
            volume_factor=float(raw.get("volume_factor", defaults.volume_factor)),
            model_version=str(raw.get("model_version", defaults.model_version)),
        )

    def weight_of(self, severity: Severity) -> float:
        return self.severity_weights.get(severity.value, 0.0)


@dataclass(frozen=True, slots=True)
class CategoryScore:
    """One category's aggregate."""

    category: str
    score: float
    findings: int
    failed: int
    worst_severity: Severity = Severity.INFO

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "score": round(self.score, 2),
            "findings": self.findings,
            "failed": self.failed,
            "worst_severity": self.worst_severity.value,
        }


@dataclass(frozen=True, slots=True)
class ScanScore:
    """The whole scan's aggregate."""

    score: float
    categories: tuple[CategoryScore, ...] = ()
    total_findings: int = 0
    total_failed: int = 0
    model_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 2),
            "total_findings": self.total_findings,
            "total_failed": self.total_failed,
            "model_version": self.model_version,
            "categories": [c.to_dict() for c in self.categories],
        }


class ScoreEngine:
    """Computes risk scores. Pure, stateless, and deterministic.

    New score levels are added as methods rather than by changing existing ones, which is how the
    brief's "extensions without modifying existing analyzers" requirement is met concretely.
    """

    #: The 0-10 ceiling every score is expressed on.
    MAX_SCORE = 10.0

    def __init__(self, config: ScoringConfig | None = None) -> None:
        self.config = config or ScoringConfig()

    def score_finding(self, severity: Severity, confidence: float, status: PluginOutcome) -> float:
        """``severity_weight x confidence``, or zero when nothing was established.

        Multiplying by confidence is the load-bearing choice: a critical finding nobody is sure of
        should not outrank a high-severity one that is certain.
        """
        if status is not PluginOutcome.FAIL:
            return 0.0
        return round(self.config.weight_of(severity) * max(0.0, min(1.0, confidence)), 4)

    def score_category(self, category: str, findings: list[Finding]) -> CategoryScore:
        """The worst finding in a category, nudged upward by how many others also failed."""
        failures = [f for f in findings if f.status is PluginOutcome.FAIL]
        if not failures:
            return CategoryScore(category=category, score=0.0, findings=len(findings), failed=0)

        worst = max(f.risk_score for f in failures)
        additional = len(failures) - 1
        volume = min(additional * self.config.volume_factor, self.MAX_SCORE - worst)
        worst_severity = max(
            (f.severity for f in failures),
            key=self.config.weight_of,
            default=Severity.INFO,
        )

        return CategoryScore(
            category=category,
            score=round(min(worst + max(volume, 0.0), self.MAX_SCORE), 4),
            findings=len(findings),
            failed=len(failures),
            worst_severity=worst_severity,
        )

    def score_scan(self, findings: list[Finding]) -> ScanScore:
        """Weighted mean of category scores.

        A mean rather than a max, because a scan is a statement about a whole system: one broken
        category among ten is a different situation from ten broken categories, and a max cannot
        tell them apart.
        """
        by_category: dict[str, list[Finding]] = {}
        for finding in findings:
            by_category.setdefault(finding.category or "uncategorized", []).append(finding)

        categories = [
            self.score_category(category, group) for category, group in sorted(by_category.items())
        ]

        weighted = 0.0
        total_weight = 0.0
        for category in categories:
            weight = self.config.category_weights.get(category.category, 1.0)
            weighted += category.score * weight
            total_weight += weight

        return ScanScore(
            score=round(weighted / total_weight, 4) if total_weight else 0.0,
            categories=tuple(categories),
            total_findings=len(findings),
            total_failed=sum(1 for f in findings if f.status is PluginOutcome.FAIL),
            model_version=self.config.model_version,
        )


def load_scoring_config(path: Path) -> ScoringConfig:
    """Load from YAML or JSON, falling back to defaults on any problem."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        return ScoringConfig()
    return ScoringConfig.from_mapping(raw) if isinstance(raw, dict) else ScoringConfig()


__all__ = [
    "CategoryScore",
    "ScanScore",
    "ScoreEngine",
    "ScoringConfig",
    "load_scoring_config",
]
