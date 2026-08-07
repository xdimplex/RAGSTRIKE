"""``Finding`` -- the Analyzer Engine's output, and the only thing downstream consumers read.

**A Finding is authored by the analyzer, never by a plugin.** A plugin reports what it observed; the
analyzer decides what that means. The distinction is the whole point of this phase: severity, risk,
and confidence on a Finding come from configurable rules applied to observations, not from values a
plugin assigned itself.

That matters because a plugin's own verdict is written by whoever wrote the plugin. Two packs might
both call something HIGH while meaning different things by it. Re-deriving every rating in one place
against one rule set is what makes findings comparable across packs, and what lets an operator
re-tune severity without editing a single plugin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
import uuid

from ragstrike.models.values.enums import PluginOutcome, Severity


@dataclass(frozen=True, slots=True)
class Finding:
    """One standardized security finding.

    Attributes:
        id: Unique identifier for this finding.
        scan_id: The scan that produced it.
        plugin_id: Which plugin's observations it was derived from. Provenance, not authority --
            the plugin supplied the observation, the analyzer reached the conclusion.
        category: The plugin's category (``prompt_injection``, ``context_poisoning``, ...). Used to
            group findings and to select category-scoped rules and recommendations.
        status: ``PASS`` / ``FAIL`` / ``INCONCLUSIVE``, decided by the rule engine. ``ERROR`` and
            ``SKIPPED`` survive from the observation because they describe the *run* rather than
            the target, and rewriting them as a security verdict would be a lie.
        severity: How bad this is if real. Assigned by rules, not copied from the plugin.
        confidence: ``0.0``-``1.0``, how sure the analyzer is.
        confidence_band: ``low`` / ``medium`` / ``high`` -- the same number, bucketed, because a
            report reads better with a word and an operator filters better with a number.
        risk_score: ``0.0``-``10.0``. Deterministic arithmetic over severity and confidence, never
            a model call (ADR-011). Reproducible by hand from the finding's own fields.
        evidence: Normalized evidence. One shape regardless of which plugin produced it.
        recommendation: Retrieved advice, never generated at analysis time.
        references: Supporting links, from the recommendation mapping.
        timestamp: When the analyzer produced this finding.
        notes: Human-readable trace of how the verdict was reached -- which rules fired, what the
            plugin originally said. A finding that cannot explain itself is one nobody will act on.
        analyzer_version: Which analyzer produced it. A finding is only interpretable against the
            rules that generated it, so the version travels with it.
        metadata: Anything else worth carrying, including the original plugin outcome.
    """

    id: str
    scan_id: str
    plugin_id: str
    category: str
    status: PluginOutcome
    severity: Severity
    confidence: float = 0.0
    confidence_band: str = "low"
    risk_score: float = 0.0
    evidence: dict[str, Any] = field(default_factory=dict)
    recommendation: str = ""
    references: tuple[str, ...] = ()
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    notes: str = ""
    analyzer_version: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex

    @property
    def is_vulnerability(self) -> bool:
        """Only ``FAIL`` asserts a weakness.

        ``INCONCLUSIVE`` is deliberately excluded: an undetermined result is not evidence of
        weakness any more than of strength, and counting it either way would put a number in a
        report that no observation supports.
        """
        return self.status is PluginOutcome.FAIL

    @property
    def is_determinate(self) -> bool:
        return self.status in {PluginOutcome.PASS, PluginOutcome.FAIL}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "scan_id": self.scan_id,
            "plugin_id": self.plugin_id,
            "category": self.category,
            "status": self.status.value,
            "severity": self.severity.value,
            "confidence": round(self.confidence, 4),
            "confidence_band": self.confidence_band,
            "risk_score": round(self.risk_score, 2),
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "references": list(self.references),
            "timestamp": self.timestamp.isoformat(),
            "notes": self.notes,
            "analyzer_version": self.analyzer_version,
            "metadata": self.metadata,
        }


__all__ = ["Finding"]
