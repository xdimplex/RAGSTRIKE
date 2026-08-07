"""Progress counts the work a scan does, not the packs its profile filtered out.

WHY THIS FILE EXISTS
    A ``smoke`` scan runs 2 of the 9 installed packs. It displayed **"7 / 9 cases" within one
    second**, then sat apparently stalled for a minute while the two real packs ran.

    Nothing was wrong with the scan. The progress endpoint was adding ``plugins_skipped`` to the
    numerator, and the scheduler emits every skip in a single block before any work begins -- so
    the bar filled up with the profile's own filtering and had two ticks left for the part that
    takes time. The finished-scan path had the same shape: "9 / 9" regardless of what ran.

    The whole suite passed throughout. The arithmetic lived inline in the route, where no test
    could reach it without a running server; extracting it is half the fix.

WHAT THIS DOES NOT CHANGE
    Coverage. It still divides by ``plugins_total`` and still reports 22% for a smoke scan, because
    it answers a different question -- see the docstring on ``progress_counts``. The tests below
    assert that the two numbers are allowed to disagree, since making them agree is the obvious
    wrong fix.
"""

from __future__ import annotations

import pytest

from ragstrike.api.routers.scans import progress_counts
from ragstrike.models.entities.scan import ScanSession


def session(*, total: int, executed: int, skipped: int) -> ScanSession:
    return ScanSession(
        id="s1",
        target_id="t1",
        target_name="vulnerable-rag",
        plugins_total=total,
        plugins_executed=executed,
        plugins_skipped=skipped,
    )


def test_a_finished_smoke_scan_reads_as_complete() -> None:
    """2 packs of 9 selected, both run. The operator should see 2 / 2, not 9 / 9 or 7 / 9."""
    assert progress_counts(session(total=9, executed=2, skipped=7)) == (2, 2, 100.0)


def test_a_smoke_scan_halfway_through_is_halfway_through() -> None:
    """The old code reported 8 / 9 (89%) here -- for a scan that had done one pack of two."""
    completed, total, percent = progress_counts(session(total=9, executed=1, skipped=7))

    assert (completed, total) == (1, 2)
    assert percent == 50.0


def test_a_scan_that_has_not_started_shows_no_progress() -> None:
    completed, total, percent = progress_counts(session(total=9, executed=0, skipped=7))

    assert (completed, total, percent) == (0, 2, 0.0)


def test_a_full_coverage_scan_is_unaffected() -> None:
    """``standard`` skips nothing, so the change must be invisible there."""
    assert progress_counts(session(total=9, executed=9, skipped=0)) == (9, 9, 100.0)


def test_progress_and_coverage_are_allowed_to_disagree() -> None:
    """The point of the fix, stated as a test.

    A smoke scan is 100% finished and covers 22% of the surface. Anyone "fixing" the apparent
    inconsistency by making progress divide by ``plugins_total`` reintroduces the original bug.
    """
    s = session(total=9, executed=2, skipped=7)
    _, _, percent = progress_counts(s)
    coverage = s.plugins_executed / s.plugins_total

    assert percent == 100.0
    assert coverage == pytest.approx(0.222, abs=0.001)


def test_everything_skipped_does_not_divide_by_zero() -> None:
    """A profile whose packs are all unavailable: no work to do, and no crash reporting it."""
    assert progress_counts(session(total=9, executed=0, skipped=9)) == (0, 0, 0.0)


def test_the_counter_cannot_exceed_its_denominator() -> None:
    """Defensive: a bar past 100% reads as a bug in the scan rather than in the arithmetic."""
    completed, total, percent = progress_counts(session(total=9, executed=5, skipped=7))

    assert completed <= total
    assert percent <= 100.0
