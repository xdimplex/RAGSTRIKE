"""``ConfidenceEngine`` -- how sure the analyzer is, as a number and as a word.

Confidence answers "how much should a reader trust this finding", which is a different question from
severity ("how bad is it if true"). Conflating them produces reports where a certain-but-minor issue
outranks a probable-but-critical one.

**Both forms are produced, because both are needed.** A numeric score sorts and filters; a band
(`low`/`medium`/`high`) reads. Deriving the band from the number keeps them from disagreeing.

Every input is configurable. The defaults encode one judgement worth stating: **evidence matters
more than a plugin's self-assessment.** A plugin claiming 0.9 with nothing recorded should be
trusted less than one claiming 0.6 and showing its working, because the second can be checked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ragstrike.analyzers.base.observation import Observation
from ragstrike.analyzers.evidence.evidence_engine import NormalizedEvidence


@dataclass(frozen=True, slots=True)
class ConfidenceConfig:
    """Tunable weights and thresholds."""

    #: How much the plugin's own confidence contributes.
    plugin_weight: float = 0.5
    #: How much recorded evidence contributes.
    evidence_weight: float = 0.3
    #: How much repeated agreement across cases contributes.
    corroboration_weight: float = 0.2

    #: Subtracted when a finding carries no evidence at all.
    no_evidence_penalty: float = 0.3
    #: Subtracted when the run errored -- an incomplete run supports weaker conclusions.
    error_penalty: float = 0.2

    #: Band thresholds. A score at or above the value takes that band.
    high_threshold: float = 0.75
    medium_threshold: float = 0.4

    #: Signals beyond this add nothing. Ten detectors agreeing is not meaningfully more convincing
    #: than three, and without a ceiling a noisy pack would outrank a careful one on volume alone.
    corroboration_cap: int = 3

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> ConfidenceConfig:
        weights = raw.get("weights") or {}
        penalties = raw.get("penalties") or {}
        bands = raw.get("bands") or {}
        defaults = cls()
        return cls(
            plugin_weight=float(weights.get("plugin", defaults.plugin_weight)),
            evidence_weight=float(weights.get("evidence", defaults.evidence_weight)),
            corroboration_weight=float(weights.get("corroboration", defaults.corroboration_weight)),
            no_evidence_penalty=float(penalties.get("no_evidence", defaults.no_evidence_penalty)),
            error_penalty=float(penalties.get("error", defaults.error_penalty)),
            high_threshold=float(bands.get("high", defaults.high_threshold)),
            medium_threshold=float(bands.get("medium", defaults.medium_threshold)),
            corroboration_cap=int(raw.get("corroboration_cap", defaults.corroboration_cap)),
        )


@dataclass(frozen=True, slots=True)
class ConfidenceResult:
    """A confidence score, its band, and why."""

    score: float
    band: str
    components: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "band": self.band,
            "components": {k: round(v, 4) for k, v in self.components.items()},
        }


class ConfidenceEngine:
    """Computes confidence. Pure and stateless."""

    def __init__(self, config: ConfidenceConfig | None = None) -> None:
        self.config = config or ConfidenceConfig()

    def compute(
        self,
        observation: Observation,
        evidence: NormalizedEvidence,
        *,
        modifier: float = 0.0,
    ) -> ConfidenceResult:
        """Score how much this finding should be trusted.

        Args:
            observation: The plugin's raw result.
            evidence: Its normalized evidence.
            modifier: Adjustment from matched rules, applied before clamping.
        """
        config = self.config

        plugin = _clamp(observation.reported_confidence) * config.plugin_weight
        has_evidence = 0.0 if evidence.is_empty else config.evidence_weight
        corroboration = (
            min(len(evidence.signals), config.corroboration_cap)
            / config.corroboration_cap
            * config.corroboration_weight
            if config.corroboration_cap
            else 0.0
        )

        score = plugin + has_evidence + corroboration
        components = {
            "plugin": plugin,
            "evidence": has_evidence,
            "corroboration": corroboration,
        }

        if evidence.is_empty:
            score -= config.no_evidence_penalty
            components["no_evidence_penalty"] = -config.no_evidence_penalty
        if observation.error:
            score -= config.error_penalty
            components["error_penalty"] = -config.error_penalty
        if modifier:
            score += modifier
            components["rule_modifier"] = modifier

        final = _clamp(score)
        return ConfidenceResult(score=final, band=self.band_for(final), components=components)

    def band_for(self, score: float) -> str:
        """Bucket *score* into ``low`` / ``medium`` / ``high``."""
        if score >= self.config.high_threshold:
            return "high"
        if score >= self.config.medium_threshold:
            return "medium"
        return "low"


def _clamp(value: float) -> float:
    """Clamp to ``0.0``-``1.0`` rather than raising -- arithmetic overshooting by a rounding error
    should not crash an analysis run."""
    return max(0.0, min(1.0, value))


def load_confidence_config(path: Path) -> ConfidenceConfig:
    """Load from YAML or JSON, falling back to defaults on any problem.

    Defaults are sensible, so a missing or malformed file degrades to standard behaviour rather
    than to no confidence scoring at all.
    """
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        return ConfidenceConfig()
    return ConfidenceConfig.from_mapping(raw) if isinstance(raw, dict) else ConfidenceConfig()


__all__ = [
    "ConfidenceConfig",
    "ConfidenceEngine",
    "ConfidenceResult",
    "load_confidence_config",
]
