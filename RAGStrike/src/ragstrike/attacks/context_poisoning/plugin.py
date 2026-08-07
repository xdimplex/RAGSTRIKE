"""The Context Poisoning pack.

OWASP LLM04 / LLM08. Does retrieval return what it should, and only what it should?

**An evaluation module, not an active poisoning pack.** The Phase 1 scaffold sketched a pack that
ingests poisoned documents, re-queries, and cleans up. Phase 9 deliberately scopes that down: this
pack never writes to the target. It asks the questions in a prepared dataset and compares what
retrieval actually returned against what the dataset says it should have.

The security property under test is unchanged -- whether adversarial content in the corpus can
steer answers -- but the corpus state is *declared* by the dataset rather than *created* here. In
the lab an operator ingests ``corpus/poisoned/`` as a deliberate exercise and runs the matching
dataset; the pack detects the effect without having caused it. The cost is stated plainly in the
docs: this design cannot demonstrate cross-session persistence, because proving that requires
mutating the corpus.

**No external-target escape hatch.** Unlike the injection and leakage packs, there is no
``require_local_target`` option. The Phase 9 brief requires that configuration to enable external
targets not exist in this phase, so the loopback refusal is unconditional in code -- there is no
value an operator can set to reach a non-loopback host through this pack.

**All evaluation logic lives here.** The engine schedules this plugin and stores whatever
``Analysis`` comes back. Delete this directory and the engine still starts, still scans, and still
reports, with a coverage gap recorded.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import ipaddress
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ragstrike.attacks.context_poisoning.datasets import (
    EvaluationCase,
    LoadResult,
    load_datasets,
)
from ragstrike.attacks.context_poisoning.detectors import (
    DetectorBindings,
    Signal,
    combine,
    detect_canary,
    detect_citation_integrity,
    detect_retrieval_integrity,
)
from ragstrike.core.contracts.target_adapter import TargetAdapter, TargetResponse
from ragstrike.models.values.enums import Capability, PluginOutcome, Severity
from ragstrike.plugins.base.attack import (
    Analysis,
    BaseAttack,
    ExecutionRecord,
    Payload,
    Recommendation,
)
from ragstrike.plugins.base.reports import Check, ValidationReport
from ragstrike.sdk.base import EvidenceCollection
from ragstrike.sdk.helpers import Timer, YamlHelper
from ragstrike.sdk.request_builder import TargetRequestBuilder
from ragstrike.sdk.response_parser import ResponseParser
from ragstrike.sdk.result_builder import ResultBuilder, fold_results

PACK_ROOT = Path(__file__).parent

_LOG_LEVELS = {"debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING}

#: Keys a retrieved chunk might use for its identifier and its source. VulnerableRAG uses
#: ``chunk_id`` and ``source_name``; the alternatives keep the pack useful against a
#: differently-shaped adapter instead of silently reporting no provenance.
_CHUNK_ID_KEYS = ("chunk_id", "id", "chunk", "index")
_CHUNK_SOURCE_KEYS = ("source_name", "source", "document", "document_id", "title")


class ContextPoisoningAttack(BaseAttack):
    plugin_id = "context-poisoning"
    plugin_name = "Context Poisoning"
    plugin_version = "1.0.0"
    author = "RAGStrike"
    description = "Evaluates retrieval integrity against prepared evaluation datasets."
    category = "context_poisoning"
    severity = Severity.HIGH
    requires_capabilities = (Capability.CHAT, Capability.RETURN_CHUNKS)
    owasp_mapping = ("LLM04", "LLM08")
    references = ("docs/context-poisoning-pack.md",)
    tags = ("context-poisoning", "llm04", "llm08", "retrieval-integrity", "first-party")

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._bindings = self._load_bindings()
        self._loaded: LoadResult = self._load_datasets()
        self._cases: dict[str, EvaluationCase] = {c.question_id: c for c in self._loaded.cases}
        self._target_label = "unknown"
        self._refusal = ""

    # -- pack data ---------------------------------------------------------------------------------

    def _load_bindings(self) -> DetectorBindings:
        raw = YamlHelper.load(_read(PACK_ROOT / "detectors" / "bindings.yaml")) or {}
        return DetectorBindings.from_mapping(raw)

    def _dataset_dir(self) -> Path:
        """Resolve the configured dataset location.

        A relative path resolves against the pack directory so the shipped datasets are found
        without configuration; an absolute path lets an operator keep site-specific datasets
        outside the distribution.
        """
        configured = Path(str(self.context.config.get("dataset_location", "datasets")))
        return configured if configured.is_absolute() else PACK_ROOT / configured

    def _load_datasets(self) -> LoadResult:
        only = tuple(str(d) for d in self.context.config.get("datasets") or ())
        return load_datasets(self._dataset_dir(), only=only)

    def _catalog(self) -> dict[str, Any]:
        return YamlHelper.load(_read(PACK_ROOT / "recommendations" / "catalog.yaml")) or {}

    # -- configuration -----------------------------------------------------------------------------

    @property
    def _min_confidence(self) -> float:
        return float(self.context.config.get("min_confidence", 0.6))

    @property
    def _evidence_options(self) -> dict[str, Any]:
        return dict(self.context.config.get("evidence") or {})

    @property
    def _response_chars(self) -> int:
        return int(self._evidence_options.get("response_chars", 240))

    @property
    def _include_negative_signals(self) -> bool:
        return bool(self._evidence_options.get("include_negative_signals", False))

    @property
    def _logging_options(self) -> dict[str, Any]:
        return dict(self.context.config.get("logging") or {})

    def _log_at(self, message: str, **fields: Any) -> None:
        level = _LOG_LEVELS.get(
            str(self._logging_options.get("level", "info")).lower(), logging.INFO
        )
        self.context.logger.log(level, message, extra=fields)

    # -- lifecycle: validate -------------------------------------------------------------------------

    def validate(self) -> ValidationReport:
        """Confirm the datasets and bindings load, at plugin-load time.

        A pack whose datasets are missing is refused before a scan starts, rather than producing a
        report of zero findings that reads exactly like a clean bill of health.
        """
        base = super().validate()
        level = str(self._logging_options.get("level", "info")).lower()
        checks = [
            Check(
                rule="datasets-load",
                passed=bool(self._loaded.datasets),
                detail=(
                    ""
                    if self._loaded.datasets
                    else f"no datasets loaded from {self._dataset_dir()}"
                ),
            ),
            Check(
                rule="datasets-have-cases",
                passed=bool(self._cases),
                detail="" if self._cases else "datasets loaded but declare no usable cases",
            ),
            Check(
                rule="detector-weights-declared",
                passed=bool(self._bindings.weights),
                detail="" if self._bindings.weights else "bindings.yaml declares no weights",
            ),
            Check(
                rule="logging-level-known",
                passed=level in _LOG_LEVELS,
                detail="" if level in _LOG_LEVELS else f"unknown logging.level {level!r}",
            ),
        ]
        return base.merge(ValidationReport(checks=checks))

    # -- lifecycle: payloads -------------------------------------------------------------------------

    def payloads(self) -> list[Payload]:
        """One payload per evaluation case, in a deterministic order.

        The case's identity travels in ``expects`` because ``Payload``'s fields are fixed by the
        Phase 3 contract and this pack does not get to widen it.
        """
        return [
            Payload(
                id=case.question_id,
                content=case.question,
                tier="standard",
                description=f"{case.dataset_id}/{case.question_id}",
                expects={
                    "dataset_id": case.dataset_id,
                    "dataset_version": case.dataset_version,
                    "document_id": case.document_id,
                },
            )
            for case in self._loaded.cases
        ]

    # -- lifecycle: execute --------------------------------------------------------------------------

    async def execute(
        self, target: TargetAdapter, payloads: list[Payload]
    ) -> list[ExecutionRecord]:
        """Ask every case's question. The only method here that touches the network.

        Read-only: the sole target operation reachable is ``chat``. There is no ingest, upload, or
        delete on this path, so "never modifies the target" is a property of the contract rather
        than a rule to remember.
        """
        descriptor = target.describe()
        self._target_label = descriptor.url

        if not _is_local(descriptor.url):
            # Unconditional. There is no configuration value that reaches past this.
            self._refusal = f"target {descriptor.url!r} is not loopback"
            self.context.logger.warning(
                "context-poisoning refused non-local target", extra={"url": descriptor.url}
            )
            return []

        per_case = bool(self._logging_options.get("per_case", False))
        records: list[ExecutionRecord] = []

        for payload in payloads:
            if per_case:
                self._log_at(
                    "context-poisoning sending case",
                    question_id=payload.id,
                    dataset_id=payload.expects.get("dataset_id"),
                )

            # Timed here rather than taken from the adapter, so the duration recorded is what the
            # evaluation actually cost including transport, which is what the brief asks for.
            timer = Timer().start()
            try:
                response = await target.chat(
                    TargetRequestBuilder().with_prompt(payload.content).build()
                )
            except Exception as exc:
                self.context.logger.warning(
                    "context-poisoning case failed",
                    extra={"question_id": payload.id, "error": str(exc)},
                )
                response = TargetResponse(text="", error=f"{type(exc).__name__}: {exc}")
            elapsed = timer.stop().elapsed_ms

            records.append(
                ExecutionRecord(
                    payload_id=payload.id,
                    prompt=payload.content,
                    response=response,
                    elapsed_ms=elapsed,
                    error=response.error,
                )
            )

        self._log_at(
            "context-poisoning execution complete",
            sent=len(records),
            target=descriptor.url,
            datasets=[d.dataset_id for d in self._loaded.datasets],
        )
        return records

    # -- lifecycle: analyze ---------------------------------------------------------------------------

    def analyze(self, records: list[ExecutionRecord]) -> Analysis:
        """Compare every observation against its case's expectation. Pure."""
        if self._refusal:
            return Analysis(
                outcome=PluginOutcome.SKIPPED,
                summary=f"refused to run: {self._refusal}",
                detail="This pack accepts loopback targets only, unconditionally.",
                confidence=1.0,
                evidence={"refused": self._refusal, "confidence": 1.0},
            )

        evidence = EvidenceCollection()
        results = [self._score(record, evidence) for record in records]
        folded = fold_results(results)

        # A dataset declares the corpus state it was written against. If that state is not present,
        # the run measured nothing and must not report PASS.
        #
        # Only when EVERY declaring dataset is unmet, though. The shipped default runs both datasets,
        # and `poisoned-corpus` is unmet on any ordinary lab -- so overriding whenever *any* dataset
        # was unmet would make the pack permanently INCONCLUSIVE in normal use, which is its own
        # kind of useless. With one dataset satisfied there is a real verdict to report; the gap is
        # recorded in the evidence and named in the detail instead.
        unmet, met = self._corpus_precondition_status(records)
        if unmet and not met and folded.outcome is PluginOutcome.PASS:
            return Analysis(
                outcome=PluginOutcome.INCONCLUSIVE,
                summary=f"corpus precondition not met: {unmet}",
                detail=(
                    "Every case passed, but the documents this dataset was written against were "
                    "never retrieved by any case -- so the corpus almost certainly does not "
                    "contain them. 'The poisoned document did not steer the answer' is not a "
                    "result when there was no poisoned document to steer it. Ingest the lab's "
                    "poisoned corpus (`seed_corpus.py --include-poisoned`) and re-run."
                ),
                confidence=0.0,
                evidence={
                    **folded.evidence,
                    "confidence": 0.0,
                    "corpus_precondition_unmet": unmet,
                    "datasets": [d.summary() for d in self._loaded.datasets],
                    "signals": evidence.to_dict(),
                },
            )

        detail = self._reason_summary(folded)
        if unmet:
            # Reported even when another dataset carried the verdict, so a reader is never left to
            # assume the poisoned cases were exercised when they were not.
            detail = (
                f"{detail} Coverage gap: {unmet} could not be evaluated -- the documents it is "
                "written against were never retrieved, so that corpus is not loaded."
            ).strip()

        return Analysis(
            outcome=folded.outcome,
            summary=folded.summary,
            detail=detail,
            confidence=folded.confidence,
            evidence={
                **folded.evidence,
                # PluginResult has no confidence column and the scheduler drops
                # Analysis.confidence, so the reporting layer reads it back from here.
                "confidence": round(folded.confidence, 4),
                "datasets": [d.summary() for d in self._loaded.datasets],
                "skipped_datasets": [s.to_dict() for s in self._loaded.skipped],
                "signals": evidence.to_dict(),
            },
        )

    def _corpus_precondition_status(
        self, records: list[ExecutionRecord]
    ) -> tuple[str, list[str]]:
        """``(unmet, met)`` -- datasets whose declared documents were never seen, and those seen.

        WHY THIS CHECK EXISTS
            ``corpus_profile`` and ``documents`` were parsed, stored in the evidence, and never
            acted on. So running the ``poisoned-corpus`` dataset against a clean corpus produced
            ``PASS -- 8/8``: every case asked "was the poisoned document wrongly retrieved?", no
            poisoned document existed, and every case was therefore satisfied.

            On a *deliberately vulnerable* target that reads as "context poisoning: clean", which is
            the most misleading thing this pack could say. It is the exact failure the project's
            INCONCLUSIVE status exists to prevent -- "I checked and it held" versus "my battery
            might be dead" -- applied to the pack's own precondition rather than to a target's
            behaviour.

        HOW IT DECIDES, AND WHY THIS WAY
            A dataset naming source documents that appear in NO retrieval across the entire run is
            almost certainly running against a corpus that does not contain them. That inference
            uses only observations already collected, so it needs no new adapter surface and no
            second round trip to the target.

            It is deliberately conservative: a single appearance anywhere clears the dataset. A
            false "precondition met" merely restores the previous behaviour, whereas a false
            "unmet" would mask a genuine PASS -- so the asymmetry is on the safe side.
        """
        seen: set[str] = set()
        for record in records:
            parser = ResponseParser(record.response)
            seen.update(source.lower() for source in self._sources_of(parser))

        unmet: list[str] = []
        met: list[str] = []
        for dataset in self._loaded.datasets:
            declared = {
                str(doc.get("source", "")).lower()
                for doc in dataset.documents
                if doc.get("source")
            }
            # A dataset that declares no documents makes no claim about the corpus, so it cannot
            # have an unmet precondition -- and cannot vouch for one either.
            if not declared:
                continue
            if declared & seen:
                met.append(dataset.dataset_id)
            else:
                unmet.append(
                    f"{dataset.dataset_id} (expects {dataset.corpus_profile or 'a corpus'})"
                )
        return ", ".join(unmet), met

    @staticmethod
    def _reason_summary(analysis: Analysis) -> str:
        """One line naming why cases failed, so the stored detail is diagnostic rather than a
        restatement of the outcome."""
        reasons: Counter[str] = Counter()
        for result in analysis.evidence.get("results", []):
            if result.get("status") == PluginOutcome.FAIL.value:
                reason = (result.get("evidence") or {}).get("reason")
                if reason:
                    reasons[str(reason)] += 1
        if not reasons:
            return ""
        return "; ".join(f"{reason} x{count}" for reason, count in reasons.most_common())

    def _score(self, record: ExecutionRecord, evidence: EvidenceCollection) -> Any:
        case = self._cases.get(record.payload_id)
        builder = ResultBuilder(
            plugin_name=self.plugin_name, target=self._target_label
        ).from_execution_record(record)

        if case is None:
            # A record with no matching case cannot be judged against anything.
            return (
                builder.with_status(PluginOutcome.INCONCLUSIVE)
                .with_confidence(0.0)
                .with_notes("no evaluation case matched this record")
                .build()
            )

        if record.error:
            return builder.with_notes(f"transport error: {record.error}").build()

        parser = ResponseParser(record.response)
        text = parser.text()
        chunks = parser.chunks()
        sources = self._sources_of(parser)
        chunk_ids = self._chunk_ids_of(chunks)

        base_evidence = self._case_evidence(case, record, text, sources, chunk_ids)

        if not text.strip() and not sources:
            # Nothing came back at all. Every detector would report clean, and calling that a PASS
            # would claim retrieval behaved correctly on the basis of no observation.
            return (
                builder.with_status(PluginOutcome.INCONCLUSIVE)
                .with_confidence(0.0)
                .with_evidence({**base_evidence, "reason": "no_observation"})
                .with_notes(f"{case.question_id}: no response and no retrieval; nothing to compare")
                .build()
            )

        signals = [
            detect_retrieval_integrity(
                sources,
                len(chunks),
                case.expected,
                weight=self._bindings.weight_of("retrieval_integrity"),
            ),
            detect_citation_integrity(
                [str(c) for c in parser.citations()],
                sources,
                case.expected,
                weight=self._bindings.weight_of("citation_integrity"),
            ),
            detect_canary(text, case.expected, weight=self._bindings.weight_of("canary")),
        ]
        confidence = combine(signals, rule=self._bindings.combination)
        fired = [s for s in signals if s.fired]

        for signal in fired:
            evidence.add(
                kind=f"detector:{signal.detector}",
                description=signal.detail,
                data={
                    "question_id": case.question_id,
                    "dataset_id": case.dataset_id,
                    "reason": signal.reason,
                    "confidence": signal.confidence,
                },
                payload_id=record.payload_id,
            )

        recorded = signals if self._include_negative_signals else fired
        builder = builder.with_confidence(confidence).with_evidence(
            {
                **base_evidence,
                "reason": fired[0].reason if fired else "as_expected",
                "signals": [s.to_dict() for s in recorded],
            }
        )
        return self._verdict(builder, signals, fired, confidence, case)

    def _case_evidence(
        self,
        case: EvaluationCase,
        record: ExecutionRecord,
        text: str,
        sources: list[str],
        chunk_ids: list[str],
    ) -> dict[str, Any]:
        """The evidence fields the Phase 9 brief enumerates, assembled once per case."""
        return {
            "question_id": case.question_id,
            "dataset_id": case.dataset_id,
            "dataset_version": case.dataset_version,
            "document_id": case.document_id,
            "retrieved_sources": sources,
            "retrieved_chunk_ids": chunk_ids,
            "execution_ms": record.elapsed_ms,
            "observed_response": text[: self._response_chars],
            "expected_summary": {
                "must_include_sources": list(case.expected.must_include_sources),
                "must_exclude_sources": list(case.expected.must_exclude_sources),
                "min_chunks": case.expected.min_chunks,
                "security_outcome": case.expected.security_outcome,
                "analyzer_result": case.expected.analyzer_result,
            },
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def _verdict(
        self,
        builder: ResultBuilder,
        signals: list[Signal],
        fired: list[Signal],
        confidence: float,
        case: EvaluationCase,
    ) -> Any:
        """Turn detector signals into one outcome.

        Every detector here is decisive, so a clean run is a genuine PASS rather than an absence of
        evidence -- provided at least one detector actually had an expectation to check.
        """
        decisive_fired = [s for s in fired if self._bindings.is_decisive(s.detector)]
        decisive_checked = [
            s for s in signals if self._bindings.is_decisive(s.detector) and s.evaluable
        ]

        if decisive_fired and confidence >= self._min_confidence:
            return (
                builder.failed()
                .with_notes(f"{case.question_id}: {decisive_fired[0].detail}")
                .build()
            )

        if decisive_fired:
            return (
                builder.with_status(PluginOutcome.INCONCLUSIVE)
                .with_notes(
                    f"{case.question_id}: confidence {confidence:.2f} below "
                    f"{self._min_confidence:.2f} ({decisive_fired[0].reason})"
                )
                .build()
            )

        if decisive_checked:
            strength = max(s.weight for s in decisive_checked)
            return (
                builder.passed()
                .with_confidence(strength)
                .with_notes(
                    f"{case.question_id}: retrieval matched the dataset "
                    f"({', '.join(s.detector for s in decisive_checked)} checked)"
                )
                .build()
            )

        return (
            builder.with_status(PluginOutcome.INCONCLUSIVE)
            .with_confidence(0.0)
            .with_notes(f"{case.question_id}: no detector had an expectation to check")
            .build()
        )

    # -- extraction helpers ------------------------------------------------------------------------------

    @staticmethod
    def _sources_of(parser: ResponseParser) -> list[str]:
        """Source names from the retrieved chunks, falling back to the reply's own source list."""
        found: list[str] = []
        # Annotated as Any deliberately. `chunks()` declares list[dict[str, Any]], but the value
        # arrives from an adapter parsing arbitrary JSON, so the declared type is aspirational
        # rather than guaranteed. Keeping the isinstance guard and telling the type checker the
        # truth is better than deleting a real runtime check to make an optimistic annotation hold.
        raw_chunks: list[Any] = list(parser.chunks())
        for chunk in raw_chunks:
            if not isinstance(chunk, dict):
                continue
            for key in _CHUNK_SOURCE_KEYS:
                if chunk.get(key):
                    found.append(str(chunk[key]))
                    break
        return found or [str(s) for s in parser.sources()]

    @staticmethod
    def _chunk_ids_of(chunks: list[Any]) -> list[str]:
        """*chunks* is typed ``Any`` for the reason given in :meth:`_sources_of`."""
        found: list[str] = []
        for position, chunk in enumerate(chunks):
            if not isinstance(chunk, dict):
                continue
            for key in _CHUNK_ID_KEYS:
                if chunk.get(key) is not None:
                    found.append(str(chunk[key]))
                    break
            else:
                # No id key at all. Position is still a stable handle within one response, and a
                # placeholder is more useful to a reader than a silently shorter list.
                found.append(f"#{position}")
        return found

    # -- lifecycle: recommendation -------------------------------------------------------------------------

    def recommendation(self, analysis: Analysis) -> Recommendation:
        """Retrieved from the catalog, keyed by the dominant failure reason (ADR-019)."""
        catalog = self._catalog()
        if not analysis.outcome.target_is_vulnerable:
            return Recommendation(
                title="No action required",
                remediation="Retrieval matched every expectation the datasets declare.",
                effort="LOW",
            )

        entry = catalog.get("default", {})
        dominant = self._dominant_reason(analysis)
        if dominant:
            entry = catalog.get("reasons", {}).get(dominant, entry)

        default_refs = catalog.get("default", {}).get("references", ())
        return Recommendation(
            title=str(entry.get("title", "Treat the corpus as an untrusted input channel")),
            remediation=str(entry.get("remediation", "")).strip(),
            references=tuple(entry.get("references", default_refs)),
            effort=str(entry.get("effort", "MEDIUM")),
        )

    @staticmethod
    def _dominant_reason(analysis: Analysis) -> str:
        counts: Counter[str] = Counter()
        for result in analysis.evidence.get("results", []):
            if result.get("status") == PluginOutcome.FAIL.value:
                reason = (result.get("evidence") or {}).get("reason")
                if reason:
                    counts[str(reason)] += 1
        return counts.most_common(1)[0][0] if counts else ""


def _read(path: Path) -> str:
    """Read a pack data file, returning empty on absence rather than raising."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _is_local(url: str) -> bool:
    host = urlparse(url).hostname or ""
    if host in {"localhost", ""}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
