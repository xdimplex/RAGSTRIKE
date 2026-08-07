"""Retrieval Consistency Evaluation. Verifies expected behaviour; exploits nothing.

The question this asks: ask the same thing three times -- do the same documents come back?

**Why this one overrides ``analyze``.** The other four evaluation plugins judge each response on
its own, which is what :class:`EvaluationAttack` handles for them. Consistency is not a property of
any single response; it only exists *between* responses. So this plugin groups the records first
and judges each group. ``judge`` is still implemented and still used -- it does the per-response
half (did this call retrieve anything at all?) -- and the group comparison is layered on top of it.

That the base class can be extended this way rather than worked around is the point: it hoists the
shared half without deciding the shape of the criterion.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from ragstrike.models.values.enums import Capability, PluginOutcome, Severity
from ragstrike.plugins.base.attack import Analysis, ExecutionRecord, Recommendation
from ragstrike.sdk.base import EvaluationAttack, Verdict
from ragstrike.sdk.response_parser import ResponseParser
from ragstrike.sdk.result_builder import ResultBuilder, fold_results

_CHUNK_SOURCE_KEYS = ("source_name", "source", "document", "document_id", "title")


class RetrievalConsistencyEvaluation(EvaluationAttack):
    plugin_id = "retrieval-consistency"
    plugin_name = "Retrieval Consistency Evaluation"
    plugin_version = "1.0.0"
    author = "RAGStrike"
    description = "Checks that an identical question retrieves an identical source set."
    category = "evaluation"
    severity = Severity.LOW
    requires_capabilities = (Capability.CHAT, Capability.RETURN_CHUNKS)
    tags = ("evaluation", "non-offensive", "determinism")

    # -- per-response half ------------------------------------------------------------------------

    def judge(
        self,
        observed: ResponseParser,
        expects: Mapping[str, Any],  # noqa: ARG002 - see the docstring
    ) -> Verdict:
        """Whether this single call retrieved anything to compare.

        Deliberately never returns FAIL: one response cannot be inconsistent with itself, so the
        strongest thing it can say is "usable" or "not usable as a data point".

        ``expects`` is unused here and that is not an oversight. This plugin's only expectation is
        ``group``, which says which responses to compare against each other -- a question that only
        has meaning in :meth:`analyze`, where more than one response is in scope. The parameter
        stays because the base class's signature defines it.
        """
        if not observed.text().strip():
            return Verdict.inconclusive("no text returned")
        if not self._sources_of(observed):
            return Verdict.inconclusive("no retrieval provenance returned")
        return Verdict.passed("retrieved a comparable source set")

    # -- between-response half --------------------------------------------------------------------

    def analyze(self, records: list[ExecutionRecord]) -> Analysis:
        """Group the repeats and compare each group's retrieved source sets. Pure."""
        groups: dict[str, list[ExecutionRecord]] = defaultdict(list)
        for record in records:
            expects = self._expectations.get(record.payload_id, {})
            groups[str(expects.get("group") or record.payload_id)].append(record)

        results = [self._judge_group(name, group) for name, group in sorted(groups.items())]
        return fold_results(results)

    def _judge_group(self, name: str, group: list[ExecutionRecord]) -> Any:
        builder = ResultBuilder(
            plugin_name=self.plugin_name or type(self).__name__, target=self._target_label
        ).for_payload(name, group[0].prompt if group else "")

        usable = [r for r in group if not r.error and ResponseParser(r.response).text().strip()]
        if len(usable) < 2:  # noqa: PLR2004 - two is the minimum for a comparison to exist
            return (
                builder.with_status(PluginOutcome.INCONCLUSIVE)
                .with_confidence(0.5)
                .with_notes(
                    f"{len(usable)} of {len(group)} repeats usable; "
                    "at least 2 are needed to compare"
                )
                .build()
            )

        observed = [frozenset(self._sources_of(ResponseParser(r.response))) for r in usable]
        if any(not sources for sources in observed):
            return (
                builder.with_status(PluginOutcome.INCONCLUSIVE)
                .with_confidence(0.5)
                .with_notes("at least one repeat returned no retrieval provenance to compare")
                .build()
            )

        distinct = set(observed)
        if len(distinct) == 1:
            return (
                builder.passed()
                .with_notes(
                    f"all {len(usable)} repeats retrieved the same {len(observed[0])} source(s)"
                )
                .build()
            )

        return (
            builder.failed()
            .with_notes(
                f"{len(distinct)} distinct source sets across {len(usable)} identical questions: "
                f"{sorted(sorted(s) for s in distinct)}"
            )
            .build()
        )

    @staticmethod
    def _sources_of(observed: ResponseParser) -> set[str]:
        """Source names from the retrieved chunks, falling back to the reply's own source list."""
        found: set[str] = set()
        for chunk in observed.chunks():
            if not isinstance(chunk, dict):
                continue
            for key in _CHUNK_SOURCE_KEYS:
                if chunk.get(key):
                    found.add(str(chunk[key]))
                    break
        return found or {str(s) for s in observed.sources()}

    def recommendation(self, analysis: Analysis) -> Recommendation:
        if analysis.outcome.target_is_vulnerable:
            return Recommendation(
                title="Make retrieval deterministic before trusting any other finding",
                remediation=(
                    "Pin the embedding model version, fix top_k, and break ranking ties on a "
                    "stable key such as chunk id rather than leaving equal scores to arbitrary "
                    "ordering. Until identical questions retrieve identical documents, every "
                    "other result in this report is a single sample rather than a measurement."
                ),
                effort="MEDIUM",
            )
        return Recommendation(
            title="No action required",
            remediation="Retrieval was stable across every repeated question.",
            effort="LOW",
        )
