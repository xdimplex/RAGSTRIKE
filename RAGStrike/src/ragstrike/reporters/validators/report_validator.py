"""``ReportValidator`` -- refuse malformed input before it becomes a report.

A report is the artifact a security decision gets made from. One built from incoherent input --
findings without ids, scores outside their range, a scan id nobody can trace -- looks exactly as
authoritative as a correct one, which is what makes silently accepting it dangerous.

**Errors block; warnings do not.** A finding with an odd confidence is still worth reporting with a
note. One with no id cannot be referenced, cited, or looked up later, so it stops the build.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ragstrike.analyzers.base.finding import Finding
from ragstrike.core.errors import RAGStrikeError
from ragstrike.models.values.enums import PluginOutcome, Severity
from ragstrike.reporters.models.report import ReportModel


class ReportValidationError(RAGStrikeError):
    """A report could not be built from the input supplied."""

    code = "report_validation_error"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    field: str
    reason: str
    finding_id: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"field": self.field, "reason": self.reason, "finding_id": self.finding_id}

    def __str__(self) -> str:
        where = f" [{self.finding_id}]" if self.finding_id else ""
        return f"{self.field}: {self.reason}{where}"


@dataclass(frozen=True, slots=True)
class ReportValidation:
    errors: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
        }

    def raise_if_invalid(self) -> None:
        if self.errors:
            raise ReportValidationError(
                f"Cannot build a report: {len(self.errors)} validation error(s).",
                hint="; ".join(str(e) for e in self.errors[:5]),
            )


class ReportValidator:
    """Validates findings before building and models after. Pure and stateless."""

    _MAX_RISK = 10.0

    def validate_findings(self, findings: list[Finding]) -> ReportValidation:
        """Check the input is coherent enough to report on."""
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []

        if not findings:
            # A warning, not an error. A scan that genuinely found nothing still deserves a report
            # saying so -- refusing would hide the most reassuring result there is.
            warnings.append(
                ValidationIssue("findings", "no findings supplied; report will be empty")
            )

        scan_ids = {f.scan_id for f in findings}
        if len(scan_ids) > 1:
            errors.append(
                ValidationIssue(
                    "scan_id",
                    f"findings span {len(scan_ids)} scans; a report covers exactly one",
                )
            )

        for finding in findings:
            untyped: Any = finding

            if not finding.id:
                errors.append(ValidationIssue("id", "missing; a finding must be referenceable"))
            if not finding.plugin_id:
                errors.append(ValidationIssue("plugin_id", "missing", finding_id=finding.id))
            if not isinstance(untyped.status, PluginOutcome):
                errors.append(
                    ValidationIssue("status", "not a PluginOutcome", finding_id=finding.id)
                )
            if not isinstance(untyped.severity, Severity):
                errors.append(ValidationIssue("severity", "not a Severity", finding_id=finding.id))
            if not isinstance(untyped.evidence, dict):
                errors.append(ValidationIssue("evidence", "not a mapping", finding_id=finding.id))

            if not 0.0 <= finding.confidence <= 1.0:
                warnings.append(
                    ValidationIssue(
                        "confidence",
                        f"{finding.confidence} outside 0.0-1.0",
                        finding_id=finding.id,
                    )
                )
            if not 0.0 <= finding.risk_score <= self._MAX_RISK:
                warnings.append(
                    ValidationIssue(
                        "risk_score",
                        f"{finding.risk_score} outside 0.0-{self._MAX_RISK}",
                        finding_id=finding.id,
                    )
                )
            if not finding.category:
                warnings.append(
                    ValidationIssue(
                        "category",
                        "missing; the finding will group under 'uncategorized'",
                        finding_id=finding.id,
                    )
                )
            if not finding.analyzer_version:
                warnings.append(
                    ValidationIssue(
                        "analyzer_version",
                        "missing; the finding cannot be traced to the rules that produced it",
                        finding_id=finding.id,
                    )
                )

        return ReportValidation(errors=tuple(errors), warnings=tuple(warnings))

    def validate_model(self, report: ReportModel) -> ReportValidation:
        """Check a built model is internally consistent.

        Catches builder bugs rather than input problems: if the risk breakdown disagrees with the
        findings list, one of them is wrong and a reader has no way to tell which.
        """
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []

        if not report.report_id:
            errors.append(ValidationIssue("report_id", "missing"))
        if not report.cover.scan_id:
            warnings.append(ValidationIssue("cover.scan_id", "missing; the report is untraceable"))

        counted = report.risk.total
        actual = len(report.vulnerabilities)
        if counted != actual:
            errors.append(
                ValidationIssue(
                    "risk_breakdown",
                    f"counts {counted} failures but the findings list holds {actual}",
                )
            )

        summary_total = (
            report.summary.passed
            + report.summary.failed
            + report.summary.inconclusive
            + report.summary.errored
            + report.summary.skipped
        )
        if report.findings and summary_total != len(report.findings):
            errors.append(
                ValidationIssue(
                    "executive_summary",
                    f"counts {summary_total} outcomes across {len(report.findings)} findings",
                )
            )

        return ReportValidation(errors=tuple(errors), warnings=tuple(warnings))


__all__ = [
    "ReportValidation",
    "ReportValidationError",
    "ReportValidator",
    "ValidationIssue",
]
