"""The INCONCLUSIVE outcome and how it folds.

Phase 6 added a fifth ``PluginOutcome``. The risk in adding a value to an enum this widely branched
on is not that the new value misbehaves -- it is that some existing table silently does not know
about it, and the gap only shows up when a real scan produces one. These tests assert exhaustive
handling rather than trusting that every site was found by grep.
"""

from __future__ import annotations

import pytest

from ragstrike.models.values.enums import PluginOutcome
from ragstrike.sdk.result_builder import ResultBuilder, fold_results


def result(status: PluginOutcome, confidence: float = 1.0):
    return (
        ResultBuilder(plugin_name="p", target="t")
        .for_payload("p1", "x")
        .with_status(status)
        .with_confidence(confidence)
        .build()
    )


# -- semantics -------------------------------------------------------------------------------------


def test_inconclusive_does_not_assert_a_vulnerability() -> None:
    """An undetermined result is not evidence of weakness any more than of strength."""
    assert PluginOutcome.INCONCLUSIVE.target_is_vulnerable is False


def test_only_fail_asserts_a_vulnerability() -> None:
    vulnerable = [o for o in PluginOutcome if o.target_is_vulnerable]

    assert vulnerable == [PluginOutcome.FAIL]


def test_inconclusive_is_not_determinate() -> None:
    assert PluginOutcome.INCONCLUSIVE.is_determinate is False


def test_only_pass_and_fail_settle_the_question() -> None:
    determinate = {o for o in PluginOutcome if o.is_determinate}

    assert determinate == {PluginOutcome.PASS, PluginOutcome.FAIL}


def test_inconclusive_round_trips_through_its_string_value() -> None:
    """The value is persisted as TEXT, so the string form is the storage format."""
    assert PluginOutcome("INCONCLUSIVE") is PluginOutcome.INCONCLUSIVE


# -- folding precedence ----------------------------------------------------------------------------


def test_inconclusive_outranks_pass() -> None:
    """The load-bearing rule. A run where some cases reached no verdict has not established that
    the target resisted, and folding it to PASS would report confidence nobody observed."""
    analysis = fold_results([result(PluginOutcome.PASS), result(PluginOutcome.INCONCLUSIVE)])

    assert analysis.outcome is PluginOutcome.INCONCLUSIVE


def test_error_outranks_inconclusive() -> None:
    analysis = fold_results([result(PluginOutcome.INCONCLUSIVE), result(PluginOutcome.ERROR)])

    assert analysis.outcome is PluginOutcome.ERROR


def test_fail_outranks_inconclusive() -> None:
    analysis = fold_results([result(PluginOutcome.INCONCLUSIVE), result(PluginOutcome.FAIL)])

    assert analysis.outcome is PluginOutcome.FAIL


def test_inconclusive_outranks_skipped() -> None:
    analysis = fold_results([result(PluginOutcome.SKIPPED), result(PluginOutcome.INCONCLUSIVE)])

    assert analysis.outcome is PluginOutcome.INCONCLUSIVE


def test_all_inconclusive_stays_inconclusive() -> None:
    analysis = fold_results([result(PluginOutcome.INCONCLUSIVE)] * 3)

    assert analysis.outcome is PluginOutcome.INCONCLUSIVE


# -- exhaustiveness --------------------------------------------------------------------------------


def test_the_fold_precedence_table_covers_every_outcome() -> None:
    from ragstrike.sdk.result_builder.builder import _OUTCOME_RANK

    assert set(_OUTCOME_RANK) == set(PluginOutcome)


def test_every_outcome_has_a_distinct_rank() -> None:
    from ragstrike.sdk.result_builder.builder import _OUTCOME_RANK

    assert len(set(_OUTCOME_RANK.values())) == len(PluginOutcome)


@pytest.mark.parametrize("outcome", list(PluginOutcome))
def test_the_console_can_render_every_outcome(outcome: PluginOutcome) -> None:
    """Both console tables are subscripted directly, so a missing entry is a KeyError mid-scan --
    after the work is done and before it is reported."""
    from ragstrike.cli.output.console import _OUTCOME_LABEL, _OUTCOME_STYLE

    assert _OUTCOME_STYLE[outcome]
    assert _OUTCOME_LABEL[outcome]
