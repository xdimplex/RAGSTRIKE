"""ResultBuilder, fold_results, and pick_recommendation tests."""

from __future__ import annotations

from datetime import UTC, datetime

from ragstrike.core.contracts.target_adapter import TargetResponse
from ragstrike.models.values.enums import PluginOutcome, Severity
from ragstrike.plugins.base.attack import ExecutionRecord, Recommendation
from ragstrike.sdk.result_builder import ResultBuilder, fold_results, pick_recommendation


def make_record(*, ok: bool = True, payload_id: str = "p1", prompt: str = "hi") -> ExecutionRecord:
    response = TargetResponse(text="answer" if ok else "", error="" if ok else "boom")
    return ExecutionRecord(payload_id=payload_id, prompt=prompt, response=response, elapsed_ms=10)


# -- ResultBuilder ------------------------------------------------------------------------------


def test_build_produces_all_specified_fields() -> None:
    result = (
        ResultBuilder(plugin_name="my-plugin", target="my-target")
        .for_payload("p1", "the payload text")
        .passed()
        .with_severity(Severity.HIGH)
        .with_confidence(0.9)
        .with_references("ref-1", "ref-2")
        .with_notes("a note")
        .build()
    )

    assert result.plugin_name == "my-plugin"
    assert result.payload_id == "p1"
    assert result.payload == "the payload text"
    assert result.target == "my-target"
    assert result.status is PluginOutcome.PASS
    assert result.severity is Severity.HIGH
    assert result.confidence == 0.9
    assert result.references == ("ref-1", "ref-2")
    assert result.notes == "a note"
    assert isinstance(result.start_time, datetime)
    assert isinstance(result.end_time, datetime)


def test_duration_ms_is_computed_from_timestamps() -> None:
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    end = datetime(2026, 1, 1, 0, 0, 1, 500000, tzinfo=UTC)

    result = ResultBuilder(plugin_name="p", target="t").started_at(start).finished_at(end).build()

    assert result.duration_ms == 1500


def test_status_helpers_set_the_right_outcome() -> None:
    builder = ResultBuilder(plugin_name="p", target="t")

    assert builder.passed().build().status is PluginOutcome.PASS
    assert builder.failed().build().status is PluginOutcome.FAIL
    assert builder.errored().build().status is PluginOutcome.ERROR
    assert builder.skipped().build().status is PluginOutcome.SKIPPED


def test_confidence_is_clamped_not_raised() -> None:
    over = ResultBuilder(plugin_name="p", target="t").with_confidence(1.5).build()
    under = ResultBuilder(plugin_name="p", target="t").with_confidence(-0.5).build()

    assert over.confidence == 1.0
    assert under.confidence == 0.0


def test_from_execution_record_seeds_identity_and_evidence() -> None:
    record = make_record(ok=True, payload_id="p42", prompt="the prompt")

    result = (
        ResultBuilder(plugin_name="p", target="t").from_execution_record(record).passed().build()
    )

    assert result.payload_id == "p42"
    assert result.payload == "the prompt"
    assert result.evidence["elapsed_ms"] == 10


def test_from_execution_record_marks_transport_failure_as_errored() -> None:
    record = make_record(ok=False)

    result = ResultBuilder(plugin_name="p", target="t").from_execution_record(record).build()

    assert result.status is PluginOutcome.ERROR


def test_to_dict_is_json_shaped() -> None:
    import json

    result = ResultBuilder(plugin_name="p", target="t").for_payload("p1", "x").passed().build()

    json.dumps(result.to_dict())  # must not raise


# -- fold_results ---------------------------------------------------------------------------------


def build_result(status: PluginOutcome, confidence: float = 1.0) -> object:
    return (
        ResultBuilder(plugin_name="p", target="t")
        .for_payload("p", "x")
        .with_status(status)
        .with_confidence(confidence)
        .build()
    )


def test_fold_empty_results_is_skipped() -> None:
    analysis = fold_results([])

    assert analysis.outcome is PluginOutcome.SKIPPED


def test_fold_all_pass_yields_pass() -> None:
    analysis = fold_results([build_result(PluginOutcome.PASS), build_result(PluginOutcome.PASS)])

    assert analysis.outcome is PluginOutcome.PASS


def test_fold_any_fail_wins_over_everything() -> None:
    """The core precedence rule: one FAIL among many PASSes still means vulnerable."""
    results = [
        build_result(PluginOutcome.PASS),
        build_result(PluginOutcome.PASS),
        build_result(PluginOutcome.FAIL),
        build_result(PluginOutcome.ERROR),
    ]

    analysis = fold_results(results)

    assert analysis.outcome is PluginOutcome.FAIL


def test_fold_error_outranks_pass_when_no_fail_present() -> None:
    results = [build_result(PluginOutcome.PASS), build_result(PluginOutcome.ERROR)]

    assert fold_results(results).outcome is PluginOutcome.ERROR


def test_fold_confidence_averages_the_deciding_results() -> None:
    results = [
        build_result(PluginOutcome.FAIL, confidence=0.8),
        build_result(PluginOutcome.FAIL, confidence=0.4),
        build_result(PluginOutcome.PASS, confidence=1.0),  # not a FAIL, excluded from the average
    ]

    analysis = fold_results(results)

    assert analysis.confidence == 0.6


def test_fold_evidence_includes_every_result() -> None:
    results = [build_result(PluginOutcome.PASS), build_result(PluginOutcome.FAIL)]

    analysis = fold_results(results)

    assert analysis.evidence["count"] == 2
    assert len(analysis.evidence["results"]) == 2


def test_fold_summary_can_be_overridden() -> None:
    analysis = fold_results([build_result(PluginOutcome.PASS)], summary="custom summary")

    assert analysis.summary == "custom summary"


# -- pick_recommendation ---------------------------------------------------------------------------


def test_pick_recommendation_returns_none_for_empty_list() -> None:
    assert pick_recommendation([]) is None


def test_pick_recommendation_prefers_fail_over_pass() -> None:
    fail_rec = Recommendation(title="fix it", remediation="...")
    pass_rec = Recommendation(title="looks fine", remediation="...")

    results = [
        ResultBuilder(plugin_name="p", target="t").passed().with_recommendation(pass_rec).build(),
        ResultBuilder(plugin_name="p", target="t").failed().with_recommendation(fail_rec).build(),
    ]

    assert pick_recommendation(results) is fail_rec


def test_pick_recommendation_returns_none_when_nothing_carries_one() -> None:
    results = [ResultBuilder(plugin_name="p", target="t").passed().build()]

    assert pick_recommendation(results) is None
