"""``ValidationEngine`` -- refuse malformed observations before they become findings.

**Rejection is loud, and that is the point.** A malformed observation silently dropped produces a
scan report with one fewer finding and no indication anything went wrong -- which reads exactly like
a clean result. Every rejection here carries a field name and a reason, and the engine records them
on the report rather than discarding them.

The rules are deliberately minimal. This validates that an observation is *structurally usable*, not
that its contents are sensible: an observation with a strange confidence is still analyzable, while
one with no plugin id cannot be attributed to anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ragstrike.analyzers.base.observation import Observation
from ragstrike.models.values.enums import PluginOutcome


@dataclass(frozen=True, slots=True)
class ValidationError:
    """One reason an observation was refused."""

    field: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "reason": self.reason}

    def __str__(self) -> str:
        return f"{self.field}: {self.reason}"


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """The outcome of validating one observation."""

    errors: tuple[ValidationError, ...] = ()
    warnings: tuple[ValidationError, ...] = field(default_factory=tuple)

    @property
    def valid(self) -> bool:
        """Warnings never block. An observation with an odd-looking confidence is still worth
        analyzing; one missing its identity is not."""
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }


class ValidationEngine:
    """Validates observations. Pure and stateless."""

    #: Confidence outside this range means a plugin miscalculated. Warned rather than rejected --
    #: the observation is still analyzable, and the analyzer clamps before use.
    _VALID_CONFIDENCE = (0.0, 1.0)

    def validate(self, observation: Observation) -> ValidationReport:
        """Check *observation* is structurally usable."""
        errors: list[ValidationError] = []
        warnings: list[ValidationError] = []

        # Read through an Any-typed view for the type checks below. `Observation` declares
        # `reported_status: PluginOutcome` and `evidence: dict`, but a validator that trusts its
        # own annotations is not a validator -- observations are built from stored JSON and from
        # callers outside the type checker's reach, which is the case this method exists to catch.
        untyped: Any = observation

        if not observation.plugin_id:
            errors.append(
                ValidationError("plugin_id", "missing; a finding cannot be attributed without it")
            )
        if not observation.scan_id:
            errors.append(
                ValidationError("scan_id", "missing; a finding cannot be filed against a scan")
            )
        if not isinstance(untyped.reported_status, PluginOutcome):
            errors.append(ValidationError("reported_status", "not a PluginOutcome"))

        low, high = self._VALID_CONFIDENCE
        if not low <= observation.reported_confidence <= high:
            warnings.append(
                ValidationError(
                    "reported_confidence",
                    f"{observation.reported_confidence} outside {low}-{high}; will be clamped",
                )
            )
        if observation.execution_ms < 0:
            warnings.append(ValidationError("execution_ms", "negative duration"))
        if not observation.category:
            warnings.append(
                ValidationError(
                    "category",
                    "missing; category-scoped rules and recommendations will not match",
                )
            )
        if not isinstance(untyped.evidence, dict):
            errors.append(ValidationError("evidence", "not a mapping"))

        return ValidationReport(errors=tuple(errors), warnings=tuple(warnings))

    def validate_all(
        self, observations: list[Observation]
    ) -> tuple[list[Observation], list[tuple[Observation, ValidationReport]]]:
        """Split *observations* into the analyzable and the refused.

        Returns both halves rather than filtering, so the caller can record what it rejected. A
        validator that silently drops its input is indistinguishable from one that found nothing
        wrong.
        """
        accepted: list[Observation] = []
        rejected: list[tuple[Observation, ValidationReport]] = []
        for observation in observations:
            report = self.validate(observation)
            if report.valid:
                accepted.append(observation)
            else:
                rejected.append((observation, report))
        return accepted, rejected


__all__ = ["ValidationEngine", "ValidationError", "ValidationReport"]
