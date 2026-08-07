"""``EvidenceEngine`` -- one evidence shape, whatever the plugin produced.

Every pack records evidence differently. The injection pack writes detector signals; the leakage
pack writes redacted response summaries; the poisoning pack writes retrieved sources and chunk ids.
A report that has to understand three shapes will understand two of them and quietly mishandle the
third.

This normalizes all of it into one structure with named sections, so a consumer reads
``evidence.sources`` without knowing which pack filled it in.

**Normalization never invents.** A section absent from the input is absent from the output, not
defaulted to something plausible. An empty ``sources`` list means the plugin reported no sources --
which is a fact worth preserving, and quite different from "this plugin does not deal in sources".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ragstrike.analyzers.base.observation import Observation

#: Keys a plugin might use for the same concept. Checked in order; the first present wins. Packs
#: were written independently, so this is a translation table rather than a spec.
_SOURCE_KEYS = ("retrieved_sources", "sources", "citations")
_CHUNK_KEYS = ("retrieved_chunk_ids", "chunk_ids", "chunks")
_TEXT_KEYS = ("observed_response", "response", "excerpt", "text")


@dataclass(frozen=True, slots=True)
class NormalizedEvidence:
    """Evidence in one shape.

    Attributes:
        summary: One-line human-readable description of what happened.
        text: Observed response text, where the plugin recorded any. May be redacted by the plugin
            -- the engine preserves whatever it was given and never attempts to reverse it.
        signals: Detector signals, flattened across cases. The reason a finding is believable.
        sources: Retrieved or cited sources, deduplicated in first-seen order.
        chunk_ids: Retrieved chunk identifiers.
        cases: Per-case results, when the plugin recorded them.
        timing: Execution durations.
        structured: Everything else the plugin recorded, verbatim. Nothing is discarded just
            because this engine did not anticipate it.
        attachments: Reserved. Always empty today -- the field exists so a future attachment has
            somewhere to arrive without a shape change.
    """

    summary: str = ""
    text: str = ""
    signals: tuple[dict[str, Any], ...] = ()
    sources: tuple[str, ...] = ()
    chunk_ids: tuple[str, ...] = ()
    cases: tuple[dict[str, Any], ...] = ()
    timing: dict[str, Any] = field(default_factory=dict)
    structured: dict[str, Any] = field(default_factory=dict)
    attachments: tuple[dict[str, Any], ...] = ()

    @property
    def is_empty(self) -> bool:
        """Whether anything was actually recorded. Drives the "no evidence" confidence penalty."""
        return not (self.text or self.signals or self.sources or self.cases)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "text": self.text,
            "signals": list(self.signals),
            "sources": list(self.sources),
            "chunk_ids": list(self.chunk_ids),
            "cases": list(self.cases),
            "timing": self.timing,
            "structured": self.structured,
            "attachments": list(self.attachments),
        }


class EvidenceEngine:
    """Normalizes plugin evidence. Pure and stateless."""

    #: Keys lifted into named sections, so they are not duplicated into ``structured``.
    _LIFTED = frozenset(
        {*_SOURCE_KEYS, *_CHUNK_KEYS, *_TEXT_KEYS, "results", "signals", "confidence"}
    )

    def normalize(self, observation: Observation) -> NormalizedEvidence:
        """Fold *observation*'s evidence into one shape."""
        raw = observation.evidence if isinstance(observation.evidence, dict) else {}
        cases = observation.case_results

        return NormalizedEvidence(
            summary=str(observation.observed.get("summary", "")),
            text=self._first_text(raw, cases),
            signals=tuple(self._collect_signals(raw, cases)),
            sources=tuple(self._collect(raw, cases, _SOURCE_KEYS)),
            chunk_ids=tuple(self._collect(raw, cases, _CHUNK_KEYS)),
            cases=tuple(cases),
            timing={
                "execution_ms": observation.execution_ms,
                "payloads_executed": observation.payloads_executed,
            },
            structured={k: v for k, v in raw.items() if k not in self._LIFTED},
        )

    @staticmethod
    def _first_text(raw: dict[str, Any], cases: list[dict[str, Any]]) -> str:
        """The first response text found, at the top level or in a case."""
        for key in _TEXT_KEYS:
            value = raw.get(key)
            if isinstance(value, str) and value:
                return value
        for case in cases:
            evidence = case.get("evidence")
            if not isinstance(evidence, dict):
                continue
            for key in _TEXT_KEYS:
                value = evidence.get(key)
                if isinstance(value, str) and value:
                    return value
        return ""

    @staticmethod
    def _collect_signals(raw: dict[str, Any], cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Detector signals from wherever a pack put them.

        Two shapes are in use: a top-level ``signals`` accumulator (``{"count": n, "items": [...]}``)
        and per-case ``evidence.signals`` lists. Both are collected -- a pack may write either or
        both, and dropping one shape would lose the working of half the findings.
        """
        found: list[dict[str, Any]] = []

        top = raw.get("signals")
        if isinstance(top, dict) and isinstance(top.get("items"), list):
            found.extend(i for i in top["items"] if isinstance(i, dict))
        elif isinstance(top, list):
            found.extend(i for i in top if isinstance(i, dict))

        for case in cases:
            evidence = case.get("evidence")
            if isinstance(evidence, dict) and isinstance(evidence.get("signals"), list):
                found.extend(s for s in evidence["signals"] if isinstance(s, dict))

        return found

    @staticmethod
    def _collect(
        raw: dict[str, Any], cases: list[dict[str, Any]], keys: tuple[str, ...]
    ) -> list[str]:
        """Values for *keys*, deduplicated in first-seen order.

        Order is preserved rather than sorted because the first source retrieved is usually the
        most relevant one, and sorting would discard that for no gain.
        """
        seen: dict[str, None] = {}

        def take(container: dict[str, Any]) -> None:
            for key in keys:
                value = container.get(key)
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, str | int):
                            seen.setdefault(str(item), None)
                        elif isinstance(item, dict):
                            # A chunk dict rather than a bare name. Take whichever identifying
                            # field it carries.
                            for inner in ("source_name", "source", "chunk_id", "id"):
                                if item.get(inner):
                                    seen.setdefault(str(item[inner]), None)
                                    break
                    break

        take(raw)
        for case in cases:
            evidence = case.get("evidence")
            if isinstance(evidence, dict):
                take(evidence)

        return list(seen)


__all__ = ["EvidenceEngine", "NormalizedEvidence"]
