"""Tests for the validation harness itself.

WHY THE HARNESS NEEDS ITS OWN TESTS
    It is the thing that says whether the framework works. A bug in it produces a *confident wrong
    answer* about the framework's correctness, which is worse than no validation at all — a red build
    gets investigated, a falsely green one does not.

    The specific failure to guard against is a check or comparison that passes vacuously. One already
    happened in this project: a compatibility test enumerated routes by walking an attribute that
    silently returned nothing, so "no endpoint was added" could never fail. These tests are written
    to catch that shape of mistake.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from validation.benchmarks.models import (
    Benchmark,
    BenchmarkResult,
    Comparison,
    Expectation,
    Outcome,
    Status,
    ValidationSummary,
)
from validation.runner.executor import ScanRecord, evaluate, fold
from validation.runner.loader import DatasetError, all_benchmarks, load_all, load_dataset

DATASETS = Path(__file__).resolve().parent.parent / "datasets"

#: The four dataset families the phase names: prompt manipulation, prompt leakage, context
#: evaluation, general RAG behaviour.
EXPECTED_DATASETS = 4

#: One VALIDATED, one VALIDATED, one NOT_RUN in the pass-rate fixture below.
SUMMARY_FIXTURE_SIZE = 3


def result(**kwargs: object) -> BenchmarkResult:
    defaults: dict[str, object] = {
        "benchmark_id": "B-1",
        "description": "d",
        "target": "vulnerable-rag",
        "plugins_executed": ("p",),
        "expected": Outcome.FAIL,
        "observed": Outcome.FAIL,
        "status": Status.VALIDATED,
        "execution_ms": 1,
    }
    defaults.update(kwargs)
    return BenchmarkResult(**defaults)  # type: ignore[arg-type]  # keyword construction


# -- the shipped datasets --------------------------------------------------------------------------


def test_every_shipped_dataset_loads() -> None:
    """If the datasets do not load, nothing else in this harness means anything."""
    datasets = load_all(DATASETS)

    assert len(datasets) >= EXPECTED_DATASETS, "expected the four dataset families the phase names"


def test_the_four_named_categories_are_present() -> None:
    categories = {dataset.category for dataset in load_all(DATASETS)}

    assert categories == {
        "prompt_manipulation",
        "prompt_leakage",
        "context_evaluation",
        "general_behaviour",
    }


def test_every_benchmark_declares_both_halves_of_the_lab() -> None:
    """A benchmark with only one target cannot separate them, which is what the suite is for."""
    for benchmark in all_benchmarks(load_all(DATASETS)):
        assert set(benchmark.targets) == {"vulnerable-rag", "secure-rag"}, benchmark.id


def test_every_expectation_carries_a_rationale() -> None:
    """An expectation with no reasoning is a number someone will later change to make the suite
    green. The rationale is what makes that visibly wrong."""
    for benchmark in all_benchmarks(load_all(DATASETS)):
        for expectation in benchmark.expectations:
            assert expectation.rationale, f"{benchmark.id}/{expectation.target}"


def test_every_dataset_states_its_success_criteria() -> None:
    for dataset in load_all(DATASETS):
        assert dataset.success_criteria, dataset.id
        assert dataset.purpose, dataset.id


def test_benchmark_ids_are_unique_across_every_dataset() -> None:
    ids = [b.id for b in all_benchmarks(load_all(DATASETS))]

    assert len(ids) == len(set(ids))


def test_most_benchmarks_expect_the_two_halves_to_differ() -> None:
    """The suite's whole purpose.

    Not *every* benchmark: the general-behaviour dataset deliberately expects both halves to PASS,
    because it exists to catch SecureRAG scoring well by being broken. But a suite where most
    benchmarks expected the same outcome from both would be measuring something other than the
    difference.
    """
    benchmarks = all_benchmarks(load_all(DATASETS))
    differing = [
        b
        for b in benchmarks
        if b.expectation_for("vulnerable-rag").outcome  # type: ignore[union-attr]  # asserted above
        != b.expectation_for("secure-rag").outcome  # type: ignore[union-attr]
    ]

    assert len(differing) > len(benchmarks) / 2


# -- loader validation -----------------------------------------------------------------------------


def test_a_malformed_dataset_names_the_field(tmp_path: Path) -> None:
    """A typo in a dataset produces a benchmark that quietly expects the wrong thing. Validation
    turns that into a startup error naming the file."""
    bad = tmp_path / "bad.yaml"
    bad.write_text("dataset:\n  id: x\nbenchmarks: []\n", encoding="utf-8")

    with pytest.raises(DatasetError, match="non-empty list"):
        load_dataset(bad)


def test_an_invalid_outcome_is_refused(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "dataset:\n  id: x\nbenchmarks:\n  - id: B\n    description: d\n"
        "    plugins: [p]\n    expectations:\n      - target: t\n        outcome: MAYBE\n",
        encoding="utf-8",
    )

    with pytest.raises(DatasetError, match="not a valid outcome"):
        load_dataset(bad)


def test_a_duplicate_benchmark_id_is_refused(tmp_path: Path) -> None:
    """A duplicate would make one benchmark silently shadow another in every report."""
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "dataset:\n  id: x\nbenchmarks:\n"
        "  - id: B\n    description: d\n    plugins: [p]\n"
        "    expectations: [{target: t, outcome: PASS}]\n"
        "  - id: B\n    description: e\n    plugins: [p]\n"
        "    expectations: [{target: t, outcome: PASS}]\n",
        encoding="utf-8",
    )

    with pytest.raises(DatasetError, match="duplicate benchmark id"):
        load_dataset(bad)


def test_an_empty_directory_is_refused(tmp_path: Path) -> None:
    """Silently validating nothing would report a perfect pass rate over zero benchmarks."""
    with pytest.raises(DatasetError, match="no dataset files"):
        load_all(tmp_path)


# -- outcome folding -------------------------------------------------------------------------------


def test_fold_follows_the_engine_precedence() -> None:
    from ragstrike.models.values.enums import PluginOutcome

    assert fold([PluginOutcome.PASS, PluginOutcome.FAIL]) is PluginOutcome.FAIL
    assert fold([PluginOutcome.PASS, PluginOutcome.INCONCLUSIVE]) is PluginOutcome.INCONCLUSIVE
    assert fold([PluginOutcome.PASS, PluginOutcome.SKIPPED]) is PluginOutcome.PASS
    assert fold([]) is PluginOutcome.SKIPPED


# -- evaluation ------------------------------------------------------------------------------------


def benchmark(outcome: Outcome = Outcome.FAIL) -> Benchmark:
    return Benchmark(
        id="B-1",
        description="d",
        category="c",
        plugins=("prompt-injection",),
        expectations=(Expectation(target="vulnerable-rag", outcome=outcome),),
    )


def test_a_failed_scan_is_not_run_rather_than_a_mismatch() -> None:
    """An unreachable target is an environment problem. Counting it as a framework defect would make
    a stopped Ollama look like a broken scanner."""
    record = ScanRecord(target="vulnerable-rag", error="TargetUnreachableError: refused")

    outcome = evaluate(benchmark(), "vulnerable-rag", record)

    assert outcome.status is Status.NOT_RUN
    assert "refused" in outcome.detail


def test_a_missing_plugin_is_not_run_rather_than_a_mismatch() -> None:
    record = ScanRecord(target="vulnerable-rag", results={})

    outcome = evaluate(benchmark(), "vulnerable-rag", record)

    assert outcome.status is Status.NOT_RUN
    assert "not installed" in outcome.detail


def test_an_unexpected_inconclusive_is_undetermined_not_a_mismatch() -> None:
    """The framework declined to claim. Weaker evidence than a wrong claim, and reported as such."""
    from datetime import UTC, datetime

    from ragstrike.models.entities.scan import PluginResult
    from ragstrike.models.values.enums import PluginOutcome

    record = ScanRecord(
        target="vulnerable-rag",
        results={
            "prompt-injection": PluginResult(
                id="r",
                scan_id="s",
                plugin_slug="prompt-injection",
                plugin_version="1.0.0",
                outcome=PluginOutcome.INCONCLUSIVE,
                created_at=datetime.now(UTC),
            )
        },
    )

    outcome = evaluate(benchmark(Outcome.FAIL), "vulnerable-rag", record)

    assert outcome.status is Status.UNDETERMINED


def test_an_expected_inconclusive_validates() -> None:
    """Some checks cannot be established from outside the target, and the framework saying so is a
    successful validation of its honesty -- not a gap."""
    from datetime import UTC, datetime

    from ragstrike.models.entities.scan import PluginResult
    from ragstrike.models.values.enums import PluginOutcome

    record = ScanRecord(
        target="vulnerable-rag",
        results={
            "prompt-injection": PluginResult(
                id="r",
                scan_id="s",
                plugin_slug="prompt-injection",
                plugin_version="1.0.0",
                outcome=PluginOutcome.INCONCLUSIVE,
                created_at=datetime.now(UTC),
            )
        },
    )

    outcome = evaluate(benchmark(Outcome.INCONCLUSIVE), "vulnerable-rag", record)

    assert outcome.status is Status.VALIDATED


# -- comparison ------------------------------------------------------------------------------------


def test_a_comparison_validates_only_when_both_halves_matched() -> None:
    comparison = Comparison(
        benchmark_id="B-1",
        description="d",
        vulnerable=result(observed=Outcome.FAIL, status=Status.VALIDATED),
        secure=result(
            target="secure-rag",
            expected=Outcome.PASS,
            observed=Outcome.FAIL,
            status=Status.MISMATCH,
        ),
    )

    assert comparison.status is Status.MISMATCH


def test_a_comparison_reports_whether_it_separated_the_targets() -> None:
    """The column that matters. Both halves matching their own expectation while observing the same
    outcome has validated nothing about the difference between them."""
    same = Comparison(
        benchmark_id="B",
        description="d",
        vulnerable=result(observed=Outcome.PASS, expected=Outcome.PASS),
        secure=result(target="secure-rag", observed=Outcome.PASS, expected=Outcome.PASS),
    )
    differing = Comparison(
        benchmark_id="B",
        description="d",
        vulnerable=result(observed=Outcome.FAIL),
        secure=result(target="secure-rag", observed=Outcome.PASS, expected=Outcome.PASS),
    )

    assert same.status is Status.VALIDATED
    assert not same.separates
    assert differing.separates
    assert differing.difference == "FAIL -> PASS"


def test_a_comparison_is_not_run_when_either_half_could_not_run() -> None:
    """Found by running the harness: the first version reported every skipped benchmark as a
    MISMATCH, which is the difference between "you disabled some plugins" and "the scanner is
    broken". The summary totals were right; the comparison table was not."""
    comparison = Comparison(
        benchmark_id="B-1",
        description="d",
        vulnerable=result(observed=Outcome.SKIPPED, status=Status.NOT_RUN),
        secure=result(target="secure-rag", observed=Outcome.SKIPPED, status=Status.NOT_RUN),
    )

    assert comparison.status is Status.NOT_RUN


def test_an_incomplete_comparison_is_not_run() -> None:
    comparison = Comparison(benchmark_id="B", description="d", vulnerable=result(), secure=None)

    assert comparison.status is Status.NOT_RUN
    assert comparison.difference == "incomplete"


# -- summary ---------------------------------------------------------------------------------------


def test_benchmarks_that_could_not_run_are_excluded_from_the_pass_rate() -> None:
    """Folding them in would make an environment problem look like a framework defect."""
    summary = ValidationSummary(
        results=(
            result(status=Status.VALIDATED),
            result(status=Status.VALIDATED),
            result(status=Status.NOT_RUN),
        )
    )

    assert summary.total == SUMMARY_FIXTURE_SIZE
    assert summary.not_run == 1
    assert summary.pass_rate == 1.0


def test_a_summary_with_nothing_that_ran_reports_zero_rather_than_dividing_by_zero() -> None:
    summary = ValidationSummary(results=(result(status=Status.NOT_RUN),))

    assert summary.pass_rate == 0.0


def test_the_summary_serializes_every_field_the_phase_names() -> None:
    payload = ValidationSummary(results=(result(),)).to_dict()
    entry = payload["results"][0]

    for field in (
        "benchmark_id",
        "description",
        "target",
        "plugins_executed",
        "expected_outcome",
        "observed_outcome",
        "status",
        "execution_ms",
        "timestamp",
    ):
        assert field in entry, f"missing {field}"


# -- consistency and performance -------------------------------------------------------------------


def test_the_consistency_checks_cover_everything_the_phase_names() -> None:
    from validation.runner.consistency import CHECKS

    names = {name for name, _ in CHECKS}

    for required in (
        "Plugin discovery",
        "Configuration loading",
        "Analyzer output",
        "Finding generation",
        "Report generation",
        "Database integrity",
        "Logging",
        "Dashboard integration",
    ):
        assert required in names, f"missing check: {required}"


def test_a_check_that_raises_is_a_failed_check_not_a_crashed_run() -> None:
    from validation.runner.consistency import _timed

    outcome = _timed("boom", lambda: (_ for _ in ()).throw(RuntimeError("nope")))

    assert not outcome.passed
    assert "RuntimeError" in outcome.detail


def test_no_target_requested_is_a_skip_rather_than_a_failure() -> None:
    """Reporting FAIL would make "I did not ask for a target" indistinguishable from "the target is
    down"."""
    from validation.runner.consistency import check_target_communication

    passed, detail = check_target_communication([])

    assert passed
    assert "skipped" in detail


def test_performance_measurements_carry_their_caveat() -> None:
    """A table of precise-looking milliseconds invites comparison it cannot support."""
    from validation.runner.performance import Measurement, summarize

    payload = summarize([Measurement("x", 1.0, "ms")])

    assert "single-sample" in payload["caveat"].lower()
