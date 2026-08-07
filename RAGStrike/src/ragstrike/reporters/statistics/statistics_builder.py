"""``StatisticsBuilder`` -- how the scan ran, as opposed to what it found.

Kept separate from the executive summary on purpose. "Three criticals" and "the scan took four
minutes" answer different questions for different readers, and mixing them produces a summary a
security lead skims past.
"""

from __future__ import annotations

from ragstrike.analyzers.base.finding import Finding
from ragstrike.reporters.models.report import ScanStatistics


class StatisticsBuilder:
    """Builds the scan statistics section. Pure and stateless."""

    def build(
        self,
        findings: list[Finding],
        *,
        duration_ms: int = 0,
        framework_version: str = "",
        analyzer_version: str = "",
        scoring_model_version: str = "",
    ) -> ScanStatistics:
        """Summarize execution.

        Durations come from each finding's recorded ``execution_ms`` rather than from wall-clock
        arithmetic here, so the numbers agree with what the analyzer stored. Recomputing them would
        let a report disagree with its own evidence.
        """
        durations = [self._duration_of(f) for f in findings]
        plugins = {f.plugin_id for f in findings}

        slowest_name, slowest_ms = "", 0
        for finding in findings:
            ms = self._duration_of(finding)
            if ms > slowest_ms:
                slowest_name, slowest_ms = finding.plugin_id, ms

        return ScanStatistics(
            duration_ms=duration_ms or sum(durations),
            plugin_count=len(plugins),
            finding_count=len(findings),
            average_plugin_ms=sum(durations) / len(durations) if durations else 0.0,
            slowest_plugin=slowest_name,
            slowest_plugin_ms=slowest_ms,
            analyzer_version=analyzer_version,
            framework_version=framework_version,
            scoring_model_version=scoring_model_version,
        )

    @staticmethod
    def _duration_of(finding: Finding) -> int:
        """Execution time from a finding's metadata.

        Zero when absent rather than raising: a finding that did not record a duration is still a
        finding, and losing the whole report over a missing timing field would be a poor trade.
        """
        raw = finding.metadata.get("execution_ms", 0)
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0


__all__ = ["StatisticsBuilder"]
