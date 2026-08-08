"""A scan listing must not report a clean sheet on a scan it did not look at.

WHY THIS FILE EXISTS
    Every row of Scan History rendered::

        47cce83…  vulnerable-rag  FAIL  grade A  risk 0.0  findings 0  plugins 0  6m36s  22%

    ``FAIL`` beside ``grade A`` on the same row, for a target the scanner had just broken into.

    The listing passed no findings to the serializer, and every derived field was computed from
    that empty list: ``findings_count`` was ``len([])``, ``risk_score`` was ``max(..., default=0)``,
    and the grader read "no findings" as "nothing bad was found" and returned **A**. Only
    ``outcome`` was right, because it reads the persisted counters.

    The distinction the code was missing is between *"I looked and found nothing"* and *"I did not
    look"*. Those produced identical arguments, so they produced identical output. They are now
    different parameters, and the second one grades ``?``.

    A 23-minute full-coverage scan of the hardened lab displayed exactly the same way, so this was
    not a rare edge -- it was every row the console had ever shown.
"""

from __future__ import annotations

import pytest

from ragstrike.api.routers.scans import _grade, _to_out
from ragstrike.models.entities.scan import ScanSession


def session(**kwargs: object) -> ScanSession:
    base: dict[str, object] = {
        "id": "47cce83d3e9f4512a327b7409e2f4859",
        "target_id": "t1",
        "target_name": "vulnerable-rag",
        "plugins_total": 9,
        "plugins_executed": 2,
        "plugins_failed": 1,
        "plugins_skipped": 7,
    }
    base.update(kwargs)
    return ScanSession(**base)  # type: ignore[arg-type]


# ------------------------------------------------------------------------------------------------
# Grading
# ------------------------------------------------------------------------------------------------


def test_unmeasured_findings_grade_as_unknown_not_as_a() -> None:
    """The exact defect. Nothing was loaded, so nothing can be graded."""
    assert _grade(0, 0.0, session(), measured=False) == "?"


def test_measured_and_genuinely_clean_grades_a() -> None:
    """The other half: a scan that really did find nothing deserves its A.

    ``plugins_failed=0`` matters. The default fixture has a failing pack, and a failing pack with
    no recorded finding is a contradiction rather than a clean sheet -- see the test below.
    """
    assert _grade(0, 0.0, session(plugins_failed=0), measured=True) == "A"


def test_a_failing_pack_with_no_finding_is_not_an_a() -> None:
    """The two facts disagree, so the grade must not pick the flattering one.

    A pack reported FAIL and the analyzer recorded nothing. Either it did not run or its output was
    not stored; both mean the risk is unknown, and "A" would assert a clean result on missing data.
    """
    assert _grade(0, 0.0, session(plugins_failed=1), measured=True) == "?"
    assert _grade(0, 0.0, session(plugins_failed=0, plugins_errored=2), measured=True) == "?"


@pytest.mark.parametrize(
    ("worst", "letter"),
    [(9.5, "F"), (9.0, "F"), (7.2, "D"), (5.0, "C"), (3.1, "B"), (2.9, "A")],
)
def test_risk_maps_to_a_letter(worst: float, letter: str) -> None:
    assert _grade(1, worst, session(), measured=True) == letter


def test_a_scan_that_executed_nothing_is_never_graded() -> None:
    """Coverage of zero means no evidence, however the findings were supplied."""
    assert _grade(0, 0.0, session(plugins_executed=0), measured=True) == "?"


# ------------------------------------------------------------------------------------------------
# Serialization
# ------------------------------------------------------------------------------------------------


def test_a_listing_row_reports_real_findings_from_the_batched_summary() -> None:
    """What the listing now passes: (count, worst_risk) from one query for the whole page."""
    out = _to_out(session(), summary=(4, 7.5))

    assert out.findings_count == 4
    assert out.risk_score == 7.5
    assert out.grade == "D"
    assert out.outcome == "FAIL"


def test_fail_with_no_findings_is_never_graded_a() -> None:
    """The contradiction, stated as precisely as it actually holds.

    ``FAIL`` and ``A`` are NOT inherently contradictory: FAIL means a payload landed, A means the
    worst finding scored under 3.0. A scanner that broke in and found only something trivial is
    entitled to say both, and the first draft of this test wrongly forbade it.

    The nonsense is FAIL with grade A and **zero findings** -- a clean letter awarded on no
    evidence at all, which is what every row of Scan History used to show.
    """
    for summary in [(0, 0.0), None]:
        out = _to_out(session(), summary=summary)  # type: ignore[arg-type]
        assert out.findings_count == 0
        assert out.grade == "?", f"graded {out.grade!r} on no evidence (summary={summary})"

    # ... while a real low-risk finding may legitimately grade A beside a FAIL.
    low = _to_out(session(), summary=(1, 2.0))
    assert (low.outcome, low.grade, low.findings_count) == ("FAIL", "A", 1)


def test_without_findings_or_summary_the_row_is_ungraded() -> None:
    """The old default. It must now read as "unknown" rather than as "clean"."""
    out = _to_out(session())

    assert out.grade == "?"
    assert out.findings_count == 0


def test_the_executed_count_survives_a_listing() -> None:
    """`plugins_executed` is a list on the wire and a count on the session.

    The listing cannot fill the list without a query per row, so it sent an empty one and the
    dashboard -- which renders its length -- showed PLUGINS 0 for a scan that ran two packs.
    """
    out = _to_out(session(), summary=(0, 0.0))

    assert out.plugins_executed == []
    assert out.plugins_executed_count == 2


def test_name_and_profile_reach_the_wire() -> None:
    """Both were declared by the schema, rendered by the dashboard, and never populated."""
    out = _to_out(session(name="nightly vulnerable sweep", profile="standard"), summary=(0, 0.0))

    assert out.name == "nightly vulnerable sweep"
    assert out.profile == "standard"


def test_an_unnamed_scan_still_gets_something_readable() -> None:
    """A column of 32-character hex is not an identifier a human can use."""
    out = _to_out(session(), summary=(0, 0.0))

    assert out.name == "scan-47cce83d"
    assert len(out.name) < 32
