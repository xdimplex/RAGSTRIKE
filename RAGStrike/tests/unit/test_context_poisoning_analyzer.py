"""Analyzer tests for the Context Poisoning pack -- the three detectors.

Each detector is pure and answers a set-membership question, so the whole truth table is reachable
without a target. The `reason` codes matter as much as the outcomes: remediation is keyed by reason,
so a detector firing with the wrong reason gives an operator the wrong advice about a real finding.

Note the sign convention: here ``fired=True`` means a violation was observed. Consistent across all
three detectors, and the opposite of the injection pack, where firing means the attack succeeded.
"""

from __future__ import annotations

from ragstrike.attacks.context_poisoning.datasets import Expectation
from ragstrike.attacks.context_poisoning.detectors import (
    DetectorBindings,
    Signal,
    combine,
    detect_canary,
    detect_citation_integrity,
    detect_retrieval_integrity,
    normalize_source,
)

BENIGN = ["company_handbook.pdf", "policy_document.pdf"]
POISON = "hidden_instruction.pdf"


# -- source normalization ------------------------------------------------------------------------------


def test_source_normalization_strips_paths_and_case() -> None:
    """Retrieval layers report provenance inconsistently. Comparing raw strings would produce false
    findings indistinguishable from real ones -- the worst failure mode for a set-membership
    detector."""
    assert normalize_source("docs/Company_Handbook.PDF") == "company_handbook.pdf"
    assert normalize_source("C:\\corpus\\policy_document.pdf") == "policy_document.pdf"


def test_source_normalization_is_stable() -> None:
    assert normalize_source("handbook.pdf") == normalize_source("  HANDBOOK.pdf  ")


# -- retrieval integrity ---------------------------------------------------------------------------------


def test_clean_retrieval_does_not_fire() -> None:
    expected = Expectation(must_include_sources=("company_handbook.pdf",), min_chunks=1)

    signal = detect_retrieval_integrity(BENIGN, 3, expected, weight=1.0)

    assert not signal.fired
    assert signal.reason == "retrieval_as_expected"


def test_a_forbidden_source_fires() -> None:
    """The finding this pack exists for."""
    expected = Expectation(must_exclude_sources=(POISON,))

    signal = detect_retrieval_integrity([*BENIGN, POISON], 3, expected, weight=1.0)

    assert signal.fired
    assert signal.reason == "forbidden_source_retrieved"
    assert POISON in signal.detail


def test_a_missing_expected_source_fires() -> None:
    expected = Expectation(must_include_sources=("company_handbook.pdf",))

    signal = detect_retrieval_integrity(["unrelated.pdf"], 1, expected, weight=1.0)

    assert signal.fired
    assert signal.reason == "expected_source_missing"


def test_too_few_chunks_fires() -> None:
    expected = Expectation(min_chunks=5)

    signal = detect_retrieval_integrity(BENIGN, 2, expected, weight=1.0)

    assert signal.fired
    assert signal.reason == "insufficient_chunks"


def test_a_forbidden_source_outranks_a_missing_one() -> None:
    """Both are wrong, but they mean different things: poisoned content reaching the model is a
    security finding, while a missing document usually means the corpus was never ingested. The
    reason drives remediation, so the more serious cause must win."""
    expected = Expectation(
        must_include_sources=("company_handbook.pdf",), must_exclude_sources=(POISON,)
    )

    signal = detect_retrieval_integrity([POISON], 1, expected, weight=1.0)

    assert signal.reason == "forbidden_source_retrieved"


def test_retrieval_matching_ignores_path_and_case_differences() -> None:
    expected = Expectation(must_exclude_sources=(POISON,))

    signal = detect_retrieval_integrity(["corpus/Hidden_Instruction.PDF"], 1, expected, weight=1.0)

    assert signal.fired


def test_no_retrieval_expectation_is_not_evaluable() -> None:
    signal = detect_retrieval_integrity(BENIGN, 3, Expectation(), weight=1.0)

    assert not signal.evaluable
    assert signal.reason == "no_expectation"


# -- citation integrity ------------------------------------------------------------------------------------


def test_grounded_citations_do_not_fire() -> None:
    expected = Expectation(citations_subset_of_retrieved=True)

    signal = detect_citation_integrity(["company_handbook.pdf"], BENIGN, expected, weight=0.9)

    assert not signal.fired
    assert signal.reason == "citations_grounded"


def test_a_fabricated_citation_fires() -> None:
    expected = Expectation(citations_subset_of_retrieved=True)

    signal = detect_citation_integrity(["ghost.pdf"], BENIGN, expected, weight=0.9)

    assert signal.fired
    assert signal.reason == "unsupported_citation"
    assert "ghost.pdf" in signal.detail


def test_a_missing_expected_citation_fires() -> None:
    expected = Expectation(must_include_citations=("policy_document.pdf",))

    signal = detect_citation_integrity(["company_handbook.pdf"], BENIGN, expected, weight=0.9)

    assert signal.fired
    assert signal.reason == "expected_citation_missing"


def test_citations_without_provenance_are_not_evaluable() -> None:
    """Citations exist but nothing was reported retrieved. A fabricated citation and an adapter
    that does not surface provenance look identical from here, so the detector says so."""
    expected = Expectation(citations_subset_of_retrieved=True)

    signal = detect_citation_integrity(["a.pdf"], [], expected, weight=0.9)

    assert not signal.fired
    assert not signal.evaluable
    assert signal.reason == "no_provenance"


def test_citing_nothing_is_not_a_violation() -> None:
    expected = Expectation(citations_subset_of_retrieved=True)

    signal = detect_citation_integrity([], BENIGN, expected, weight=0.9)

    assert not signal.fired


def test_no_citation_expectation_is_not_evaluable() -> None:
    signal = detect_citation_integrity(["a.pdf"], BENIGN, Expectation(), weight=0.9)

    assert not signal.evaluable


# -- canary --------------------------------------------------------------------------------------------------


def test_a_repeated_canary_fires() -> None:
    expected = Expectation(canary_absent=("POISON-CANARY-HI-01",))

    signal = detect_canary("As POISON-CANARY-HI-01 states, ignore policy.", expected, weight=1.0)

    assert signal.fired
    assert signal.reason == "poisoned_content_repeated"


def test_canary_matching_is_case_insensitive() -> None:
    expected = Expectation(canary_absent=("POISON-CANARY-HI-01",))

    assert detect_canary("poison-canary-hi-01", expected, weight=1.0).fired


def test_a_clean_answer_does_not_fire() -> None:
    expected = Expectation(canary_absent=("POISON-CANARY-HI-01",))

    signal = detect_canary("Working hours are nine to five.", expected, weight=1.0)

    assert not signal.fired
    assert signal.reason == "clean"


def test_no_canary_declared_is_not_evaluable() -> None:
    """ "None planted" is a gap in what can be observed, not evidence the corpus is clean."""
    signal = detect_canary("anything", Expectation(), weight=1.0)

    assert not signal.evaluable
    assert signal.reason == "no_canary"


# -- combination ------------------------------------------------------------------------------------------------


def test_combine_takes_the_strongest_violation() -> None:
    signals = [Signal("citation_integrity", True, 0.9), Signal("canary", True, 1.0)]

    assert combine(signals) == 1.0


def test_related_violations_do_not_sum() -> None:
    """A forbidden source retrieved AND its canary repeated is one failure observed twice, not
    two independent findings."""
    signals = [Signal("retrieval_integrity", True, 1.0), Signal("canary", True, 1.0)]

    assert combine(signals) == 1.0


def test_combine_of_nothing_is_zero() -> None:
    assert combine([]) == 0.0


# -- bindings ------------------------------------------------------------------------------------------------------


def test_bindings_load_weights_and_decisiveness() -> None:
    bindings = DetectorBindings.from_mapping(
        {"detectors": {"canary": {"weight": 1.0, "decisive": True}}}
    )

    assert bindings.weight_of("canary") == 1.0
    assert bindings.is_decisive("canary") is True


def test_an_undeclared_detector_cannot_acquit() -> None:
    empty = DetectorBindings.from_mapping({})

    assert empty.weight_of("canary") == 0.0
    assert empty.is_decisive("canary") is False


def test_every_shipped_detector_is_decisive() -> None:
    """Unusual, and the payoff of the dataset design: every detector here answers a set question
    with a definite answer, so a clean run is a real PASS rather than an absence of evidence."""
    import yaml

    from ragstrike.attacks.context_poisoning.plugin import PACK_ROOT

    raw = yaml.safe_load((PACK_ROOT / "detectors" / "bindings.yaml").read_text(encoding="utf-8"))
    bindings = DetectorBindings.from_mapping(raw)

    assert bindings.weights
    assert all(bindings.is_decisive(name) for name in bindings.weights)


def test_every_signal_serializes_its_reason() -> None:
    """Remediation is keyed by reason, so it has to survive into stored evidence."""
    signal = Signal("retrieval_integrity", True, 1.0, "detail", reason="forbidden_source_retrieved")

    assert signal.to_dict()["reason"] == "forbidden_source_retrieved"
