"""Dataset loading and validation.

WHY THE LOADER VALIDATES RATHER THAN TRUSTS
    A benchmark dataset is the specification the framework is measured against. A typo in it does not
    produce a loud failure -- it produces a *benchmark that quietly expects the wrong thing*, and the
    run then reports a mismatch that has nothing to do with the framework. Validation here turns that
    into a startup error naming the file and the field.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from validation.benchmarks.models import Benchmark, Expectation, Outcome

DATASET_DIR = Path(__file__).resolve().parent.parent / "datasets"


class DatasetError(Exception):
    """A dataset file is malformed. Always names the file and the field."""


@dataclass(frozen=True, slots=True)
class Dataset:
    """One loaded dataset file."""

    id: str
    purpose: str
    category: str
    required_plugins: tuple[str, ...]
    success_criteria: str
    benchmarks: tuple[Benchmark, ...]
    source: Path

    @property
    def targets(self) -> tuple[str, ...]:
        seen: list[str] = []
        for benchmark in self.benchmarks:
            for target in benchmark.targets:
                if target not in seen:
                    seen.append(target)
        return tuple(seen)


def _require(mapping: dict[str, Any], key: str, where: str) -> Any:
    if key not in mapping:
        raise DatasetError(f"{where}: missing required field {key!r}")
    return mapping[key]


def load_dataset(path: Path) -> Dataset:
    """Read and validate one dataset file."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise DatasetError(f"{path.name}: not valid YAML -- {exc}") from exc

    if not isinstance(raw, dict):
        raise DatasetError(f"{path.name}: top level must be a mapping")

    meta = _require(raw, "dataset", path.name)
    if not isinstance(meta, dict):
        raise DatasetError(f"{path.name}: 'dataset' must be a mapping")

    dataset_id = str(_require(meta, "id", path.name))
    entries = _require(raw, "benchmarks", path.name)
    if not isinstance(entries, list) or not entries:
        raise DatasetError(f"{path.name}: 'benchmarks' must be a non-empty list")

    benchmarks: list[Benchmark] = []
    seen_ids: set[str] = set()

    for index, entry in enumerate(entries):
        where = f"{path.name}[{index}]"
        if not isinstance(entry, dict):
            raise DatasetError(f"{where}: each benchmark must be a mapping")

        benchmark_id = str(_require(entry, "id", where))
        if benchmark_id in seen_ids:
            # A duplicate id would make one benchmark silently shadow another in every report.
            raise DatasetError(f"{where}: duplicate benchmark id {benchmark_id!r}")
        seen_ids.add(benchmark_id)

        raw_expectations = _require(entry, "expectations", where)
        if not isinstance(raw_expectations, list) or not raw_expectations:
            raise DatasetError(f"{where}: 'expectations' must be a non-empty list")

        expectations: list[Expectation] = []
        for expectation in raw_expectations:
            if not isinstance(expectation, dict):
                raise DatasetError(f"{where}: each expectation must be a mapping")
            outcome_name = str(_require(expectation, "outcome", where)).upper()
            try:
                outcome = Outcome(outcome_name)
            except ValueError as exc:
                raise DatasetError(
                    f"{where}: {outcome_name!r} is not a valid outcome; "
                    f"expected one of {', '.join(o.value for o in Outcome)}"
                ) from exc
            expectations.append(
                Expectation(
                    target=str(_require(expectation, "target", where)),
                    outcome=outcome,
                    rationale=str(expectation.get("rationale", "")).strip(),
                    min_severity=str(expectation.get("min_severity", "")).upper(),
                )
            )

        plugins = entry.get("plugins") or []
        if not isinstance(plugins, list) or not plugins:
            raise DatasetError(f"{where}: 'plugins' must be a non-empty list")

        benchmarks.append(
            Benchmark(
                id=benchmark_id,
                description=str(_require(entry, "description", where)),
                category=str(meta.get("category", "")),
                plugins=tuple(str(p) for p in plugins),
                expectations=tuple(expectations),
                success_criteria=str(meta.get("success_criteria", "")).strip(),
                dataset_id=dataset_id,
            )
        )

    return Dataset(
        id=dataset_id,
        purpose=str(meta.get("purpose", "")).strip(),
        category=str(meta.get("category", "")),
        required_plugins=tuple(str(p) for p in meta.get("required_plugins", [])),
        success_criteria=str(meta.get("success_criteria", "")).strip(),
        benchmarks=tuple(benchmarks),
        source=path,
    )


def load_all(directory: Path | None = None) -> list[Dataset]:
    """Load every dataset in *directory*, sorted by filename for a stable report order."""
    root = directory or DATASET_DIR
    files = sorted(root.glob("*.yaml")) + sorted(root.glob("*.json"))
    if not files:
        raise DatasetError(f"no dataset files found in {root}")

    datasets = [load_dataset(path) for path in files]

    seen: dict[str, Path] = {}
    for dataset in datasets:
        if dataset.id in seen:
            raise DatasetError(
                f"duplicate dataset id {dataset.id!r} in {dataset.source.name} "
                f"and {seen[dataset.id].name}"
            )
        seen[dataset.id] = dataset.source

    return datasets


def all_benchmarks(datasets: list[Dataset]) -> list[Benchmark]:
    return [benchmark for dataset in datasets for benchmark in dataset.benchmarks]
