"""Dataset loading tests for the Context Poisoning pack.

The loader is lenient about *files* and strict about *cases*, and both halves matter. A malformed
file must not take down a scan; a case with nothing to compare against must not be kept, because it
would pass unconditionally and inflate coverage with a check that never ran.
"""

from __future__ import annotations

from pathlib import Path

from ragstrike.attacks.context_poisoning.datasets import (
    Expectation,
    load_datasets,
)
from ragstrike.attacks.context_poisoning.plugin import PACK_ROOT

SHIPPED = PACK_ROOT / "datasets"


def write(directory: Path, name: str, body: str) -> Path:
    path = directory / name
    path.write_text(body, encoding="utf-8")
    return path


VALID = """
dataset_id: "unit-test"
version: "2.1.0"
corpus_profile: "benign"
cases:
  - question_id: "q-1"
    document_id: "doc-1"
    question: "What does the handbook say?"
    expected:
      retrieval:
        must_include_sources: ["handbook.pdf"]
        must_exclude_sources: ["poison.pdf"]
        min_chunks: 2
      citations:
        must_be_subset_of_retrieved: true
      canary_absent: ["CANARY-1"]
      security_outcome: "uncompromised"
      analyzer_result: "PASS"
"""


# -- the shipped datasets ----------------------------------------------------------------------------


def test_the_shipped_datasets_load() -> None:
    result = load_datasets(SHIPPED)

    assert {d.dataset_id for d in result.datasets} == {"benign-baseline", "poisoned-corpus"}
    assert result.ok


def test_every_shipped_dataset_declares_a_version() -> None:
    """A result is only interpretable against the dataset that produced it, so an unversioned
    dataset makes its own findings unreproducible."""
    for dataset in load_datasets(SHIPPED).datasets:
        assert dataset.version and dataset.version != "0.0.0"


def test_every_shipped_case_is_checkable() -> None:
    for dataset in load_datasets(SHIPPED).datasets:
        assert dataset.cases
        assert all(c.expected.is_checkable for c in dataset.cases)


def test_shipped_cases_have_stable_unique_ids() -> None:
    ids = [c.question_id for c in load_datasets(SHIPPED).cases]

    assert len(ids) == len(set(ids))


def test_cases_are_returned_in_a_deterministic_order() -> None:
    first = [c.question_id for c in load_datasets(SHIPPED).cases]
    second = [c.question_id for c in load_datasets(SHIPPED).cases]

    assert first == second == sorted(first, key=lambda q: q)


# -- parsing ------------------------------------------------------------------------------------------


def test_a_valid_dataset_parses_every_field(tmp_path: Path) -> None:
    write(tmp_path, "d.yaml", VALID)

    dataset = load_datasets(tmp_path).datasets[0]
    case = dataset.cases[0]

    assert dataset.dataset_id == "unit-test"
    assert dataset.version == "2.1.0"
    assert dataset.corpus_profile == "benign"
    assert case.question_id == "q-1"
    assert case.document_id == "doc-1"
    assert case.expected.must_include_sources == ("handbook.pdf",)
    assert case.expected.must_exclude_sources == ("poison.pdf",)
    assert case.expected.min_chunks == 2
    assert case.expected.citations_subset_of_retrieved is True
    assert case.expected.canary_absent == ("CANARY-1",)
    assert case.expected.security_outcome == "uncompromised"
    assert case.expected.analyzer_result == "PASS"


def test_a_case_carries_its_dataset_identity(tmp_path: Path) -> None:
    """Evidence has to name the dataset and version a case came from, so the case carries them
    rather than the reader having to correlate them later."""
    write(tmp_path, "d.yaml", VALID)

    case = load_datasets(tmp_path).cases[0]

    assert case.dataset_id == "unit-test"
    assert case.dataset_version == "2.1.0"


# -- leniency about files -------------------------------------------------------------------------------


def test_a_malformed_file_is_skipped_not_fatal(tmp_path: Path) -> None:
    write(tmp_path, "bad.yaml", "cases: [unclosed\n")
    write(tmp_path, "good.yaml", VALID)

    result = load_datasets(tmp_path)

    assert [d.dataset_id for d in result.datasets] == ["unit-test"]
    assert len(result.skipped) == 1
    assert not result.ok


def test_a_non_mapping_file_is_skipped(tmp_path: Path) -> None:
    write(tmp_path, "list.yaml", "- just\n- a\n- list\n")

    result = load_datasets(tmp_path)

    assert result.datasets == ()
    assert "not a mapping" in result.skipped[0].reason


def test_a_missing_directory_is_reported_not_raised(tmp_path: Path) -> None:
    result = load_datasets(tmp_path / "nope")

    assert result.datasets == ()
    assert "not found" in result.skipped[0].reason


def test_unsupported_extensions_are_ignored_not_skipped(tmp_path: Path) -> None:
    """A README beside the datasets was never a candidate, so it must not appear as a skipped
    file -- a noisy skip list is one an operator learns to ignore."""
    write(tmp_path, "README.md", "not a dataset")
    write(tmp_path, "d.yaml", VALID)

    assert load_datasets(tmp_path).skipped == ()


def test_a_skipped_file_records_why(tmp_path: Path) -> None:
    write(tmp_path, "bad.yaml", "cases: [unclosed\n")

    assert load_datasets(tmp_path).skipped[0].reason


# -- strictness about cases ------------------------------------------------------------------------------


def test_a_case_with_no_question_is_dropped(tmp_path: Path) -> None:
    write(
        tmp_path,
        "d.yaml",
        'dataset_id: "x"\ncases:\n  - question_id: "q"\n    expected:\n'
        "      retrieval: {min_chunks: 1}\n",
    )

    result = load_datasets(tmp_path)

    assert result.datasets == ()
    assert "no usable cases" in result.skipped[0].reason


def test_a_case_with_no_id_is_dropped(tmp_path: Path) -> None:
    write(
        tmp_path,
        "d.yaml",
        'dataset_id: "x"\ncases:\n  - question: "hi?"\n    expected:\n'
        "      retrieval: {min_chunks: 1}\n",
    )

    assert load_datasets(tmp_path).datasets == ()


def test_a_case_with_nothing_to_check_is_dropped(tmp_path: Path) -> None:
    """The important one. A case declaring no expectation would pass unconditionally and count
    toward coverage -- a check that never ran, reported as one that did."""
    write(
        tmp_path,
        "d.yaml",
        'dataset_id: "x"\ncases:\n  - question_id: "q"\n    question: "hi?"\n'
        '    expected:\n      security_outcome: "uncompromised"\n',
    )

    result = load_datasets(tmp_path)

    assert result.datasets == ()
    assert "no usable cases" in result.skipped[0].reason


def test_a_good_case_survives_a_bad_sibling(tmp_path: Path) -> None:
    write(
        tmp_path,
        "d.yaml",
        'dataset_id: "x"\nversion: "1.0.0"\ncases:\n'
        '  - question_id: "bad"\n    question: ""\n    expected: {}\n'
        '  - question_id: "good"\n    question: "hi?"\n'
        "    expected:\n      retrieval: {min_chunks: 1}\n",
    )

    assert [c.question_id for c in load_datasets(tmp_path).cases] == ["good"]


# -- filtering ---------------------------------------------------------------------------------------------


def test_datasets_can_be_filtered_by_id() -> None:
    result = load_datasets(SHIPPED, only=("benign-baseline",))

    assert [d.dataset_id for d in result.datasets] == ["benign-baseline"]


def test_filtering_to_an_unknown_id_yields_nothing() -> None:
    assert load_datasets(SHIPPED, only=("does-not-exist",)).datasets == ()


# -- expectation semantics -------------------------------------------------------------------------------------


def test_an_empty_expectation_is_not_checkable() -> None:
    assert not Expectation().is_checkable


def test_any_single_expectation_makes_a_case_checkable() -> None:
    assert Expectation(must_include_sources=("a.pdf",)).is_checkable
    assert Expectation(must_exclude_sources=("p.pdf",)).is_checkable
    assert Expectation(min_chunks=1).is_checkable
    assert Expectation(citations_subset_of_retrieved=True).is_checkable
    assert Expectation(canary_absent=("C",)).is_checkable


def test_declaring_only_an_expected_outcome_is_not_checkable() -> None:
    """`security_outcome` and `analyzer_result` say what a healthy system *should* conclude. They
    are not themselves observations, so a case declaring only those checks nothing."""
    assert not Expectation(security_outcome="compromised", analyzer_result="FAIL").is_checkable


def test_dataset_summary_carries_the_version() -> None:
    summary = load_datasets(SHIPPED).datasets[0].summary()

    assert summary["dataset_version"]
    assert summary["dataset_id"]
    assert summary["cases"] > 0
