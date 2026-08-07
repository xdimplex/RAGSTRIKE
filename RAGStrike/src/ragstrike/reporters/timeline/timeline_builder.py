"""``TimelineBuilder`` -- the chronological record of a scan.

A timeline answers questions a summary cannot: which plugin took the longest, whether analysis ran
against a complete scan, how long the whole pipeline took end to end. It is also the section a
reader checks when a result looks wrong, so it must be honest about what it does *not* know.

**Ordering is by timestamp, then by a stable key.** Findings frequently share a timestamp to the
microsecond, and an unstable sort would reorder the timeline between two renders of the same report.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ragstrike.analyzers.base.finding import Finding
from ragstrike.reporters.models.report import TimelineEvent


class TimelineBuilder:
    """Builds the timeline section. Pure -- every timestamp is supplied, never read from a clock."""

    def build(
        self,
        findings: list[Finding],
        *,
        scan_started: datetime | None = None,
        scan_finished: datetime | None = None,
        analysis_started: datetime | None = None,
        analysis_finished: datetime | None = None,
        report_generated: datetime | None = None,
    ) -> tuple[TimelineEvent, ...]:
        """Assemble events in chronological order.

        Every boundary timestamp is optional because the caller may not have recorded it. A missing
        one produces no event rather than a fabricated one -- a timeline showing an invented
        "scan started" is worse than one that admits the gap.
        """
        events: list[TimelineEvent] = []

        if scan_started:
            events.append(TimelineEvent("scan_started", "Scan started", scan_started))

        for finding in sorted(findings, key=lambda f: (f.timestamp, f.plugin_id)):
            duration = self._duration_of(finding)
            events.append(
                TimelineEvent(
                    kind="plugin_finished",
                    label=f"{finding.plugin_id} finished",
                    at=finding.timestamp,
                    detail=f"{finding.status.value} ({finding.severity.value})",
                    duration_ms=duration,
                )
            )

        if scan_finished:
            events.append(TimelineEvent("scan_finished", "Scan finished", scan_finished))
        if analysis_started:
            events.append(TimelineEvent("analysis_started", "Analysis started", analysis_started))
        if analysis_finished:
            events.append(
                TimelineEvent("analysis_finished", "Analysis finished", analysis_finished)
            )

        generated = report_generated or datetime.now(UTC)
        events.append(TimelineEvent("report_generated", "Report generated", generated))

        return tuple(sorted(events, key=lambda e: (e.at, e.kind)))

    @staticmethod
    def _duration_of(finding: Finding) -> int:
        raw = finding.metadata.get("execution_ms", 0)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0


__all__ = ["TimelineBuilder"]
