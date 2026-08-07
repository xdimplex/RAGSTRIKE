"""Evaluation dataset loading for the Context Poisoning pack.

**Datasets are data, never code.** Every evaluation case lives in a YAML file under ``datasets/``.
Nothing here evaluates a template, resolves an attribute, or executes anything a dataset contains.
That is the same rule the payload loader follows (ADR-016), applied to a richer structure.

**Loading is lenient about files and strict about cases.** A malformed dataset file is skipped and
reported rather than taking the whole scan down -- one bad file should not cost you the other five.
But a case missing its question or its expectations is dropped, because a case with nothing to
compare against would silently score as a pass and inflate coverage with a check that never ran.

The shapes here mirror the Phase 9 dataset contract exactly: a dataset carries an id, a version, a
corpus profile, and its documents; a case carries a question id, a document id, the question, and
the expectations retrieval must satisfy.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class Expectation:
    """What a correctly behaving target should do for one case.

    Attributes:
        must_include_sources: Sources retrieval is expected to return. Absence is a finding.
        must_exclude_sources: Sources retrieval must NOT return -- the poisoned documents. Presence
            is the finding this pack exists for.
        min_chunks: Fewest chunks a healthy retrieval should produce. Zero disables the check.
        citations_subset_of_retrieved: Whether every citation must trace to a retrieved chunk. A
            citation that does not is fabricated, decidable as a set operation rather than a
            judgment call.
        must_include_citations: Citations the answer is expected to carry.
        canary_absent: Markers planted in poisoned documents. Their presence in an answer means the
            model read and repeated poisoned content.
        security_outcome: What the dataset author expects of a healthy system --
            ``uncompromised`` or ``compromised``.
        analyzer_result: The verdict a healthy system should produce. Recorded so a dataset can be
            self-checking: a case whose observed result differs from this is worth a reader's
            attention even when the pack scored it PASS.
    """

    must_include_sources: tuple[str, ...] = ()
    must_exclude_sources: tuple[str, ...] = ()
    min_chunks: int = 0
    citations_subset_of_retrieved: bool = False
    must_include_citations: tuple[str, ...] = ()
    canary_absent: tuple[str, ...] = ()
    security_outcome: str = "uncompromised"
    analyzer_result: str = "PASS"

    @property
    def is_checkable(self) -> bool:
        """Whether this expectation asserts anything at all.

        A case declaring no sources, no exclusions, no minimum, no citation rule and no canary has
        nothing to compare against. Such a case is dropped at load time rather than scored, because
        it would otherwise pass unconditionally and count toward coverage.
        """
        return bool(
            self.must_include_sources
            or self.must_exclude_sources
            or self.min_chunks
            or self.citations_subset_of_retrieved
            or self.must_include_citations
            or self.canary_absent
        )

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> Expectation:
        retrieval = raw.get("retrieval") or {}
        citations = raw.get("citations") or {}
        return cls(
            must_include_sources=tuple(str(s) for s in retrieval.get("must_include_sources") or ()),
            must_exclude_sources=tuple(str(s) for s in retrieval.get("must_exclude_sources") or ()),
            min_chunks=int(retrieval.get("min_chunks", 0)),
            citations_subset_of_retrieved=bool(citations.get("must_be_subset_of_retrieved", False)),
            must_include_citations=tuple(str(c) for c in citations.get("must_include") or ()),
            canary_absent=tuple(str(c) for c in raw.get("canary_absent") or ()),
            security_outcome=str(raw.get("security_outcome", "uncompromised")),
            analyzer_result=str(raw.get("analyzer_result", "PASS")),
        )


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    """One question and what retrieval should do with it."""

    question_id: str
    question: str
    expected: Expectation
    document_id: str = ""
    dataset_id: str = ""
    dataset_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "document_id": self.document_id,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
        }


@dataclass(frozen=True, slots=True)
class Dataset:
    """A versioned set of evaluation cases written against a known corpus state."""

    dataset_id: str
    version: str
    cases: tuple[EvaluationCase, ...]
    description: str = ""
    corpus_profile: str = ""
    documents: tuple[dict[str, Any], ...] = ()
    source_path: Path | None = None

    def summary(self) -> dict[str, Any]:
        """Identity for the evidence record. Version is included because a result is only
        interpretable against the dataset that produced it."""
        return {
            "dataset_id": self.dataset_id,
            "dataset_version": self.version,
            "corpus_profile": self.corpus_profile,
            "cases": len(self.cases),
        }


@dataclass(frozen=True, slots=True)
class SkippedDataset:
    """A dataset file that could not be used, and why."""

    path: Path
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {"path": str(self.path), "reason": self.reason}


@dataclass(frozen=True, slots=True)
class LoadResult:
    datasets: tuple[Dataset, ...] = ()
    skipped: tuple[SkippedDataset, ...] = ()

    @property
    def cases(self) -> list[EvaluationCase]:
        """Every case across every loaded dataset, in a deterministic order."""
        collected = [case for dataset in self.datasets for case in dataset.cases]
        return sorted(collected, key=lambda c: (c.dataset_id, c.question_id))

    @property
    def ok(self) -> bool:
        return not self.skipped


def load_datasets(directory: Path, *, only: tuple[str, ...] = ()) -> LoadResult:
    """Load every dataset under *directory*, optionally filtered to *only* those dataset ids.

    Files are read in name order so a scan is reproducible. A file that is not valid YAML, or whose
    top level is not a mapping, or which declares no usable case, is skipped and recorded rather
    than raised -- and a skipped dataset is visible in the evidence, never silent.
    """
    if not directory.is_dir():
        return LoadResult(skipped=(SkippedDataset(directory, "dataset directory not found"),))

    datasets: list[Dataset] = []
    skipped: list[SkippedDataset] = []

    for path in sorted(directory.iterdir()):
        if path.suffix.lower() not in {".yaml", ".yml", ".json"} or not path.is_file():
            continue
        try:
            dataset = _parse(path)
        except (yaml.YAMLError, ValueError, OSError) as exc:
            skipped.append(SkippedDataset(path, f"{type(exc).__name__}: {exc}"))
            continue
        if only and dataset.dataset_id not in only:
            continue
        if not dataset.cases:
            skipped.append(SkippedDataset(path, "dataset declares no usable cases"))
            continue
        datasets.append(dataset)

    return LoadResult(datasets=tuple(datasets), skipped=tuple(skipped))


def _parse(path: Path) -> Dataset:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("top level is not a mapping")

    dataset_id = str(raw.get("dataset_id") or path.stem)
    version = str(raw.get("version") or "0.0.0")

    cases: list[EvaluationCase] = []
    for entry in raw.get("cases") or []:
        if not isinstance(entry, dict):
            continue
        question = str(entry.get("question", "")).strip()
        question_id = str(entry.get("question_id", "")).strip()
        if not question or not question_id:
            # A case with no question cannot be asked, and one with no id cannot be reported
            # against. Either way there is nothing to record, so it is dropped rather than kept.
            continue
        expected = Expectation.from_mapping(entry.get("expected") or {})
        if not expected.is_checkable:
            # Nothing to compare against. Keeping it would manufacture a pass.
            continue
        cases.append(
            EvaluationCase(
                question_id=question_id,
                question=question,
                expected=expected,
                document_id=str(entry.get("document_id", "")),
                dataset_id=dataset_id,
                dataset_version=version,
            )
        )

    return Dataset(
        dataset_id=dataset_id,
        version=version,
        cases=tuple(cases),
        description=str(raw.get("description", "")).strip(),
        corpus_profile=str(raw.get("corpus_profile", "")),
        documents=tuple(d for d in raw.get("documents") or [] if isinstance(d, dict)),
        source_path=path,
    )


__all__ = [
    "Dataset",
    "EvaluationCase",
    "Expectation",
    "LoadResult",
    "SkippedDataset",
    "load_datasets",
]
