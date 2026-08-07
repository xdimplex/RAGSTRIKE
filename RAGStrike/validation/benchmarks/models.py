"""Benchmark and result types.

WHAT A BENCHMARK IS HERE
    A *claim about behaviour*, expressed so it can be checked automatically: run these plugins
    against this target and the outcome should be this. The claim is the point -- a benchmark that
    only records what happened is a log, not a validation.

WHY EXPECTATIONS ARE PER-TARGET
    The same benchmark expects opposite results from the two halves of the lab. "Prompt injection is
    detected" is a PASS for the validation when VulnerableRAG FAILs it and when SecureRAG PASSes it.
    Collapsing that into one expected value would make the differential impossible to express, which
    is the whole reason the pair exists.

WHY INCONCLUSIVE IS A FIRST-CLASS EXPECTATION
    Some checks cannot be established from outside the target -- cross-session persistence, for one.
    A benchmark that expected PASS or FAIL there would be asserting something the framework has
    correctly declined to claim, and the honest expectation is that it declines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class Outcome(StrEnum):
    """The outcomes a benchmark can expect or observe.

    Mirrors ``ragstrike.models.values.enums.PluginOutcome`` by name rather than importing it: the
    validation harness reads results over the same surface an external consumer would, and coupling
    it to an internal enum would let a rename pass unnoticed here while breaking every real client.
    """

    PASS = "PASS"  # noqa: S105 - an outcome name, not a credential
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


class Status(StrEnum):
    """Whether the *validation* succeeded -- distinct from what the scan found."""

    #: Observed matched expected.
    VALIDATED = "VALIDATED"
    #: Observed did not match expected. The framework is not behaving as documented.
    MISMATCH = "MISMATCH"
    #: The benchmark could not run: target unreachable, plugin missing, dependency down.
    NOT_RUN = "NOT_RUN"
    #: Ran, but the result cannot be judged -- the framework declined to claim, as expected.
    UNDETERMINED = "UNDETERMINED"


@dataclass(frozen=True, slots=True)
class Expectation:
    """What one target is expected to do for one benchmark."""

    target: str
    outcome: Outcome
    #: Why this outcome is expected. Read by the report, and by the next person to see it fail.
    rationale: str = ""
    #: Minimum severity that must accompany a FAIL. Empty means unconstrained.
    min_severity: str = ""


@dataclass(frozen=True, slots=True)
class Benchmark:
    """One executable claim about the framework's behaviour."""

    id: str
    description: str
    category: str
    plugins: tuple[str, ...]
    expectations: tuple[Expectation, ...]
    success_criteria: str = ""
    dataset_id: str = ""

    def expectation_for(self, target: str) -> Expectation | None:
        return next((e for e in self.expectations if e.target == target), None)

    @property
    def targets(self) -> tuple[str, ...]:
        return tuple(e.target for e in self.expectations)


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """One benchmark, run once, against one target.

    Carries every field the phase brief names, plus the rationale, so a report is readable without
    the dataset beside it.
    """

    benchmark_id: str
    description: str
    target: str
    plugins_executed: tuple[str, ...]
    expected: Outcome
    observed: Outcome
    status: Status
    execution_ms: int
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    detail: str = ""
    findings: int = 0
    severity: str = ""

    @property
    def matched(self) -> bool:
        return self.status is Status.VALIDATED

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "description": self.description,
            "target": self.target,
            "plugins_executed": list(self.plugins_executed),
            "expected_outcome": self.expected.value,
            "observed_outcome": self.observed.value,
            "status": self.status.value,
            "execution_ms": self.execution_ms,
            "timestamp": self.timestamp,
            "findings": self.findings,
            "severity": self.severity,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class Comparison:
    """One benchmark's result across both halves of the lab.

    The difference is the interesting column. Two targets agreeing on a benchmark that was supposed
    to separate them is a finding about the *framework*, not about the targets.
    """

    benchmark_id: str
    description: str
    vulnerable: BenchmarkResult | None
    secure: BenchmarkResult | None

    @property
    def difference(self) -> str:
        if self.vulnerable is None or self.secure is None:
            return "incomplete"
        if self.vulnerable.observed == self.secure.observed:
            return f"none ({self.vulnerable.observed.value} on both)"
        return f"{self.vulnerable.observed.value} -> {self.secure.observed.value}"

    @property
    def status(self) -> Status:
        """VALIDATED only when *both* halves matched their own expectation.

        A half that could not run makes the whole comparison NOT_RUN, not a mismatch. Getting this
        wrong -- as the first version did -- reports every skipped benchmark as a framework failure,
        which is the difference between "you disabled some plugins" and "the scanner is broken".
        """
        if self.vulnerable is None or self.secure is None:
            return Status.NOT_RUN
        statuses = (self.vulnerable.status, self.secure.status)
        if Status.NOT_RUN in statuses:
            return Status.NOT_RUN
        if self.vulnerable.matched and self.secure.matched:
            return Status.VALIDATED
        if Status.UNDETERMINED in statuses:
            return Status.UNDETERMINED
        return Status.MISMATCH

    @property
    def separates(self) -> bool:
        """Whether the benchmark actually distinguished the two applications.

        A benchmark that validates on both halves while observing the same outcome has validated
        nothing about the difference between them -- which is worth reporting separately from a
        mismatch.
        """
        if self.vulnerable is None or self.secure is None:
            return False
        return self.vulnerable.observed != self.secure.observed

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "description": self.description,
            "expected": {
                "vulnerable": self.vulnerable.expected.value if self.vulnerable else None,
                "secure": self.secure.expected.value if self.secure else None,
            },
            "observed": {
                "vulnerable": self.vulnerable.observed.value if self.vulnerable else None,
                "secure": self.secure.observed.value if self.secure else None,
            },
            "difference": self.difference,
            "separates": self.separates,
            "status": self.status.value,
        }


@dataclass(frozen=True, slots=True)
class ValidationSummary:
    """The whole run, in one object."""

    results: tuple[BenchmarkResult, ...] = ()
    comparisons: tuple[Comparison, ...] = ()
    started_at: str = ""
    finished_at: str = ""

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def validated(self) -> int:
        return sum(1 for r in self.results if r.status is Status.VALIDATED)

    @property
    def mismatched(self) -> int:
        return sum(1 for r in self.results if r.status is Status.MISMATCH)

    @property
    def not_run(self) -> int:
        return sum(1 for r in self.results if r.status is Status.NOT_RUN)

    @property
    def pass_rate(self) -> float:
        """Share of benchmarks that ran *and* matched.

        Benchmarks that could not run are excluded from the denominator rather than counted as
        failures -- an unreachable target is an environment problem, and folding it into the pass
        rate would make a stopped Ollama look like a framework defect.
        """
        ran = self.total - self.not_run
        return (self.validated / ran) if ran else 0.0

    @property
    def separating(self) -> int:
        return sum(1 for c in self.comparisons if c.separates)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "totals": {
                "benchmarks": self.total,
                "validated": self.validated,
                "mismatched": self.mismatched,
                "not_run": self.not_run,
                "pass_rate": round(self.pass_rate, 4),
                "comparisons": len(self.comparisons),
                "separating": self.separating,
            },
            "results": [r.to_dict() for r in self.results],
            "comparisons": [c.to_dict() for c in self.comparisons],
        }
