"""``Observation`` -- what the Analyzer Engine consumes.

**This type is why the engine needs no changes to existing plugins.** The Phase 10 brief asks that
plugins return raw execution results only, and simultaneously that no plugin change be required.
Both hold because an ``Observation`` is *derived from* a plugin's existing ``PluginResult`` rather
than produced by a rewritten plugin.

The important consequence: a plugin's own verdict arrives here as ``reported_status`` -- a field
named to make its status obvious. It is an **observation about what the plugin concluded**, not the
finding's status. The rule engine may agree with it, override it, or ignore it. Nothing downstream
reads it as authoritative.

The engine never imports a plugin, a pack, or an adapter. It reads
:class:`~ragstrike.models.entities.scan.PluginResult`, which is a domain entity, so a new pack
written next year is analyzable on the day it ships without the engine knowing it exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ragstrike.models.entities.scan import PluginResult
from ragstrike.models.values.enums import PluginOutcome


@dataclass(frozen=True, slots=True)
class Observation:
    """One plugin's raw execution result, in the shape the engine reads.

    Attributes:
        plugin_id: Which plugin produced the observation.
        plugin_name: Display name, when known.
        scan_id: The scan it belongs to.
        category: The plugin's category, used to select category-scoped rules.
        reported_status: **What the plugin concluded, not what the analyzer concludes.** An input
            signal the rules weigh.
        reported_confidence: The plugin's own confidence, where it recorded one. Same status.
        observed: What actually happened -- summary text, per-case results, detector signals.
        expected: What the plugin expected, where it declared expectations.
        evidence: Raw evidence, in whatever shape the plugin produced. Normalized later.
        execution_ms: How long the plugin took.
        target: What it ran against.
        payloads_executed: How many cases were sent.
        error: Transport or plugin error text, empty when the run was clean.
        metadata: Anything else the plugin recorded.
    """

    plugin_id: str
    scan_id: str
    category: str = ""
    plugin_name: str = ""
    reported_status: PluginOutcome = PluginOutcome.SKIPPED
    reported_confidence: float = 0.0
    observed: dict[str, Any] = field(default_factory=dict)
    expected: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    execution_ms: int = 0
    target: str = ""
    payloads_executed: int = 0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_plugin_result(
        cls,
        result: PluginResult,
        *,
        category: str = "",
        target: str = "",
    ) -> Observation:
        """Build an observation from a stored ``PluginResult``.

        Reads only fields the Phase 3 entity already has. ``confidence`` is pulled out of the
        evidence dict because ``PluginResult`` has no such column -- the packs write it there
        precisely so it survives storage, and this is the reader half of that arrangement.

        Args:
            result: The plugin's stored result.
            category: The plugin's category, from its manifest. Empty is tolerated; rules that
                key on category simply will not match, which is a coverage gap rather than an error.
            target: What the scan ran against.
        """
        evidence = dict(result.evidence or {})
        reported_confidence = evidence.get("confidence", 0.0)
        try:
            confidence = float(reported_confidence)
        except (TypeError, ValueError):
            # A plugin wrote something non-numeric. Treat it as no confidence rather than
            # propagating a value the engine cannot reason about.
            confidence = 0.0

        return cls(
            plugin_id=result.plugin_slug,
            plugin_name=result.plugin_slug,
            scan_id=result.scan_id,
            category=category,
            reported_status=result.outcome,
            reported_confidence=confidence,
            observed={
                "summary": result.summary,
                "detail": result.detail,
                "results": evidence.get("results", []),
            },
            expected={},
            evidence=evidence,
            execution_ms=result.elapsed_ms,
            target=target,
            payloads_executed=result.payloads_executed,
            error=result.error,
            metadata={"plugin_version": result.plugin_version},
        )

    @property
    def case_results(self) -> list[dict[str, Any]]:
        """Per-case results, when the plugin recorded them. Empty list when it did not.

        Checks ``observed`` first and falls back to ``evidence``. Both are legitimate homes:
        :meth:`from_plugin_result` lifts them into ``observed``, but an ``Observation`` constructed
        directly -- by a test, or by a caller reading from somewhere other than a ``PluginResult`` --
        naturally leaves them where the plugin wrote them. Reading only one location made those two
        paths score differently for identical data, which silently zeroed both the failure ratio and
        the evidence contribution to confidence.
        """
        for container in (self.observed, self.evidence):
            raw = container.get("results")
            if isinstance(raw, list):
                cases = [r for r in raw if isinstance(r, dict)]
                if cases:
                    return cases
        return []

    @property
    def failed_cases(self) -> int:
        return sum(1 for r in self.case_results if r.get("status") == PluginOutcome.FAIL.value)

    @property
    def total_cases(self) -> int:
        return len(self.case_results)

    @property
    def failure_ratio(self) -> float:
        """Fraction of cases that failed.

        The exploitability measurement in miniature: "worked every time" and "worked once in ten"
        are different findings, and a rule set that cannot tell them apart cannot grade them
        differently.
        """
        return self.failed_cases / self.total_cases if self.total_cases else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "plugin_name": self.plugin_name,
            "scan_id": self.scan_id,
            "category": self.category,
            "reported_status": self.reported_status.value,
            "reported_confidence": self.reported_confidence,
            "execution_ms": self.execution_ms,
            "target": self.target,
            "payloads_executed": self.payloads_executed,
            "error": self.error,
            "metadata": self.metadata,
        }


__all__ = ["Observation"]
