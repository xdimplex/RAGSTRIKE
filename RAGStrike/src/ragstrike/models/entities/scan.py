"""Scan session and per-plugin result records.

These are the two things Phase 3 persists. Everything richer -- probes, signals, findings, scores --
arrives in later phases; the shape here is deliberately the minimum that a full scan lifecycle
produces, so that later phases extend it rather than replace it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
import uuid

from ragstrike.models.values.enums import PluginOutcome, ScanState


@dataclass(frozen=True, slots=True)
class PluginResult:
    """What one plugin did against one target during one scan."""

    id: str
    scan_id: str
    plugin_slug: str
    plugin_version: str
    outcome: PluginOutcome
    summary: str = ""
    detail: str = ""
    recommendation: str = ""
    payloads_executed: int = 0
    elapsed_ms: int = 0
    error: str = ""
    #: Free-form plugin output. Phase 6 replaces this with structured evidence.
    evidence: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "scan_id": self.scan_id,
            "plugin_slug": self.plugin_slug,
            "plugin_version": self.plugin_version,
            "outcome": self.outcome.value,
            "summary": self.summary,
            "detail": self.detail,
            "recommendation": self.recommendation,
            "payloads_executed": self.payloads_executed,
            "elapsed_ms": self.elapsed_ms,
            "error": self.error,
            "evidence": self.evidence,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class ScanSession:
    """One execution of the framework against one target.

    Mutable, unlike most entities here: the state machine advances in place as the scan runs, and
    the repository writes the current value at each transition. A frozen record would mean
    reconstructing the whole object on every step for no benefit.
    """

    id: str
    target_id: str
    target_name: str
    state: ScanState = ScanState.QUEUED
    engine_version: str = ""
    plugin_inventory: dict[str, str] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    #: Operator-supplied label, so a scan is findable by what it was for rather than by its hex id.
    #: Falls back to the id when blank -- see ``display_name``.
    name: str = ""
    #: The profile this scan ran. Stored because a FAIL at 22% coverage and a FAIL at 100% are
    #: different claims, and the profile is what distinguishes them in a listing.
    profile: str = ""
    plugins_total: int = 0
    plugins_executed: int = 0
    plugins_passed: int = 0
    plugins_failed: int = 0
    plugins_errored: int = 0
    plugins_skipped: int = 0
    error: str = ""

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex

    @property
    def display_name(self) -> str:
        """What a human should see in a list. The label if there is one, else a short id.

        Never the full 32-character hex: it is unreadable at a glance, identical in shape to every
        other scan, and sorts by nothing meaningful. A short prefix is enough to correlate a row
        with a report while staying scannable.
        """
        return self.name.strip() or f"scan-{self.id[:8]}"

    @property
    def elapsed_ms(self) -> int:
        end = self.finished_at or datetime.now(UTC)
        return int((end - self.started_at).total_seconds() * 1000)

    @property
    def coverage(self) -> float:
        """Executed / applicable, in ``[0, 1]``.

        Reported alongside every result. A scan that skipped most of its plugins and one that ran
        them all both produce "no failures" otherwise, and those are very different statements.
        """
        if self.plugins_total == 0:
            return 0.0
        return self.plugins_executed / self.plugins_total

    def record(self, outcome: PluginOutcome) -> None:
        """Fold one plugin result into the running counters."""
        if outcome is PluginOutcome.SKIPPED:
            self.plugins_skipped += 1
            return

        self.plugins_executed += 1
        if outcome is PluginOutcome.PASS:
            self.plugins_passed += 1
        elif outcome is PluginOutcome.FAIL:
            self.plugins_failed += 1
        elif outcome is PluginOutcome.ERROR:
            self.plugins_errored += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "state": self.state.value,
            "engine_version": self.engine_version,
            "plugin_inventory": self.plugin_inventory,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "plugins_total": self.plugins_total,
            "plugins_executed": self.plugins_executed,
            "plugins_passed": self.plugins_passed,
            "plugins_failed": self.plugins_failed,
            "plugins_errored": self.plugins_errored,
            "plugins_skipped": self.plugins_skipped,
            "coverage": round(self.coverage, 4),
            "elapsed_ms": self.elapsed_ms,
            "error": self.error,
        }
