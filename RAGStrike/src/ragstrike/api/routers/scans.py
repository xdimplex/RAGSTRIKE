"""Scans: start, watch, cancel, and read the findings.

WHY POST RETURNS 202 AND NOT 200
    A scan is minutes to hours. The response says "accepted, here is the id"; the result arrives via
    ``/progress``, the SSE stream, or ``/findings`` once it is done. An endpoint that blocked until a
    scan finished would time out in every proxy between the client and here.

WHY ``acknowledge`` IS REQUIRED
    This starts an attack against a live system. Over HTTP, on a local port, a ``POST /scans`` that
    ran on ``{"target": "x"}`` alone is one stray fetch away from an unintended scan. The flag makes
    intent explicit in the request itself, matching the same principle as the persisted authorization
    record it sits behind rather than replacing it.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ragstrike.api.deps import get_service
from ragstrike.api.schemas.models import (
    FindingList,
    FindingOut,
    LogLineOut,
    LogList,
    ProgressOut,
    ScanAccepted,
    ScanComparisonOut,
    ScanList,
    ScanOut,
    ScanRequest,
)
from ragstrike.api.service import ScanService
from ragstrike.models.entities.scan import ScanSession
from ragstrike.models.values.enums import PluginOutcome

#: Outcome -> log level, so the log pane can colour lines meaningfully. A FAIL is a security finding
#: rather than a malfunction, so it is WARNING; an ERROR means the machinery broke and says nothing
#: about the target; a SKIP is a coverage gap worth seeing but not worth alarming about.
_LOG_LEVEL_FOR: dict[PluginOutcome, str] = {
    PluginOutcome.PASS: "INFO",
    PluginOutcome.FAIL: "WARNING",
    PluginOutcome.ERROR: "ERROR",
    PluginOutcome.INCONCLUSIVE: "WARNING",
    PluginOutcome.SKIPPED: "DEBUG",
}

router = APIRouter(prefix="/scans", tags=["scans"])

Service = Annotated[ScanService, Depends(get_service)]

_MAX_LIMIT = 200


def _to_out(
    session: ScanSession,
    *,
    executed: list[str] | None = None,
    findings: list[Any] | None = None,
    summary: tuple[int, float] | None = None,
) -> ScanOut:
    """Shape one scan for the wire.

    THREE WAYS TO SUPPLY THE FINDING NUMBERS, AND WHY
        * ``findings`` -- the detail endpoint has the rows anyway, so it passes them and gets
          per-severity counts as well.
        * ``summary`` -- ``(count, worst_risk)`` from one batched query, for the listing. It cannot
          break severity down, but it gets the count, the risk and therefore the GRADE right.
        * neither -- genuinely unknown. Renders as ungraded rather than as clean.

        The third case used to be the listing's behaviour, and it was silently wrong: an empty
        findings list is indistinguishable from "no findings were recorded", so every row showed
        ``0 findings / risk 0.0 / grade A`` beside an outcome of ``FAIL``. Passing "I did not look"
        and "I looked and found nothing" as the same value is what made that possible, so they are
        now different arguments.
    """
    rows = findings or []
    severity: dict[str, int] = {}
    for finding in rows:
        key = finding.severity.value
        severity[key] = severity.get(key, 0) + 1

    if findings is not None:
        count = len(rows)
        worst = round(max((f.risk_score for f in rows), default=0.0), 2)
        measured = True
    elif summary is not None:
        count, worst_raw = summary
        worst = round(worst_raw, 2)
        measured = True
    else:
        count, worst, measured = 0, 0.0, False

    duration = 0.0
    if session.finished_at:
        duration = (session.finished_at - session.started_at).total_seconds()

    return ScanOut(
        scan_id=session.id,
        id=session.id,
        target=session.target_name,
        # `display_name` rather than the raw label: a scan started without one still needs
        # something readable in a list, and "scan-47cce83d" beats 32 characters of hex.
        name=session.display_name,
        profile=session.profile,
        state=session.state.value,
        outcome=_outcome(session),
        started_at=session.started_at,
        finished_at=session.finished_at,
        duration_s=round(duration, 2),
        plugins_executed=executed if executed is not None else [],
        plugins_executed_count=session.plugins_executed,
        plugins_total=session.plugins_total,
        plugins_passed=session.plugins_passed,
        plugins_failed=session.plugins_failed,
        plugins_errored=session.plugins_errored,
        plugins_skipped=session.plugins_skipped,
        findings_count=count,
        severity_counts=severity,
        risk_score=worst,
        grade=_grade(count, worst, session, measured=measured),
        coverage=round(session.coverage, 4),
        error=session.error,
    )


def _outcome(session: ScanSession) -> str:
    """The headline verdict. Mirrors the fold precedence used everywhere else."""
    if session.plugins_failed:
        return "FAIL"
    if session.plugins_errored:
        return "ERROR"
    if session.plugins_executed:
        return "PASS"
    return "INCONCLUSIVE"


def _grade(count: int, worst: float, session: ScanSession, *, measured: bool) -> str:
    """A letter for the risk, or ``?`` when there is nothing to grade.

    ``?`` is not decoration. A scan with no findings and a scan whose findings were never loaded
    both have a risk of zero, and grading the second one "A" asserts something nobody measured --
    which is precisely what the listing did, on rows whose own outcome column said ``FAIL``.

    ``measured`` is what separates the two. It is a parameter rather than an inference because the
    caller is the only thing that knows whether it looked.
    """
    if not measured or not session.plugins_executed:
        return "?"
    if count == 0:
        # A pack failed, yet no finding was recorded for it. The two disagree, so the honest grade
        # is "I cannot tell" -- not "A". Reaching here means the analyzer did not run, or its
        # findings were not stored, and an A would report a clean bill of health on the strength of
        # missing data. This is the shape the whole listing used to have.
        if session.plugins_failed or session.plugins_errored:
            return "?"
        return "A"
    for threshold, letter in ((9.0, "F"), (7.0, "D"), (5.0, "C"), (3.0, "B")):
        if worst >= threshold:
            return letter
    return "A"


@router.get("", response_model=ScanList, summary="Recent scans")
async def list_scans(
    service: Service,
    limit: Annotated[int, Query(ge=1, le=_MAX_LIMIT)] = 20,
) -> ScanList:
    sessions = await service.recent(limit)
    # One extra query for the whole page, not one per row -- see FindingRepository.summarise.
    summaries = await service.findings.summarise([s.id for s in sessions])
    return ScanList(
        scans=[_to_out(s, summary=summaries.get(s.id, (0, 0.0))) for s in sessions]
    )


@router.post(
    "",
    response_model=ScanAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a scan",
)
async def start_scan(request: ScanRequest, service: Service) -> ScanAccepted:
    if not request.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Set acknowledge=true (or authorized=true) to confirm you intend to send attack "
                f"payloads at {request.target!r}."
            ),
        )
    running = await service.start(
        target_name=request.target,
        profile_name=request.profile,
        plugins=request.plugins,
        categories=request.categories,
        # The dashboard has always sent this. It was accepted by the schema and then dropped here,
        # so every scan was stored nameless and listed by raw hex id.
        name=request.name,
    )
    # Both keys carry the same value. See ScanAccepted -- the dashboard reads `id`, the rest of this
    # API says `scan_id`, and emitting only one breaks whichever client was not consulted.
    return ScanAccepted(
        scan_id=running.scan_id,
        id=running.scan_id,
        state=running.state.value,
        target=running.target,
    )


@router.get("/compare", response_model=ScanComparisonOut, summary="Posture delta between two scans")
async def compare_scans(base: str, head: str, service: Service) -> ScanComparisonOut:
    """Which findings are new, fixed, or persisting between two scans.

    THIS ROUTE MUST STAY ABOVE ``/{scan_id}``
        FastAPI matches in declaration order, so registered after it, ``/scans/compare`` binds to
        ``/scans/{scan_id}`` with ``scan_id="compare"`` and 404s. The Scan History page's Compare
        button reported exactly that as "request rejected" -- the endpoint had never been
        implemented at all, and the dashboard has called it since Phase 12 (ADR-021: the dashboard
        ships against an API surface the backend had not caught up to).

    WHAT COUNTS AS "THE SAME FINDING" ACROSS TWO SCANS
        The plugin slug. Finding ids are per-scan and never repeat, so comparing them would report
        every finding as both new and fixed. The slug is what an operator means by "is that problem
        still there".

        Only FAILED findings take part. A pack that passed has no finding to fix, and counting
        skipped packs as "fixed" would let narrowing the profile look like remediation -- the single
        most dangerous thing a comparison could get wrong.
    """
    sessions = {}
    for label, scan_id in (("base", base), ("head", head)):
        session = await service.session(scan_id)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No scan {scan_id!r} (as {label}).",
            )
        sessions[label] = session

    outs: dict[str, ScanOut] = {}
    failed: dict[str, set[str]] = {}
    for label, scan_id in (("base", base), ("head", head)):
        results = await service.results(scan_id)
        findings = await service.findings.findings_for(scan_id)
        executed = [r.plugin_slug for r in results if r.outcome is not PluginOutcome.SKIPPED]
        outs[label] = _to_out(sessions[label], executed=executed, findings=findings)
        failed[label] = {
            finding.plugin_id for finding in findings if finding.status is PluginOutcome.FAIL
        }

    return ScanComparisonOut(
        base=outs["base"],
        head=outs["head"],
        new=sorted(failed["head"] - failed["base"]),
        fixed=sorted(failed["base"] - failed["head"]),
        persisting=sorted(failed["base"] & failed["head"]),
    )


@router.get("/{scan_id}", response_model=ScanOut, summary="One scan")
async def get_scan(scan_id: str, service: Service) -> ScanOut:
    session = await service.session(scan_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No scan {scan_id!r}.")
    results = await service.results(scan_id)
    findings = await service.findings.findings_for(scan_id)
    executed = [r.plugin_slug for r in results if r.outcome is not PluginOutcome.SKIPPED]
    return _to_out(session, executed=executed, findings=findings)


def progress_counts(session: ScanSession) -> tuple[int, int, float]:
    """``(completed, total, percent)`` for a finished scan.

    PROGRESS COUNTS THE WORK, NOT THE FILTER
        ``plugins_total`` counts every installed pack, including the ones the profile never
        selected. The skipped ones are resolved in a block before any real work starts, so folding
        them into the numerator made a ``smoke`` scan -- 2 packs out of 9 -- display "7 / 9 packs"
        within a second and then sit there for a minute, and a finished one read "9 / 9" whether
        its two real packs had run or not. Both numbers described the profile, not the scan.

    WHY THIS DOES NOT CONTRADICT COVERAGE
        Coverage still divides by ``plugins_total``, and must: it answers "how much of the attack
        surface did this look at?" (ADR-020). Progress answers "is it finished?". A smoke scan
        reporting 100% progress and 22% coverage is not inconsistent -- it ran everything it
        intended to run, and that was a fifth of what exists.

    Extracted from the route so it can be tested without a running server. Inline, it never was.
    """
    total = max(session.plugins_total - session.plugins_skipped, 0)
    completed = min(session.plugins_executed, total) if total else 0
    percent = round(100.0 * completed / total, 1) if total else 0.0
    return completed, total, percent


@router.get("/{scan_id}/progress", response_model=ProgressOut, summary="Progress snapshot")
async def scan_progress(scan_id: str, service: Service) -> ProgressOut:
    """Live counters while running; the stored totals once finished.

    Falling back to the database rather than 404ing after completion is deliberate: a client that
    polls slightly too slowly should get the final state, not an error implying the scan vanished.
    """
    running = service.running(scan_id)
    if running is not None:
        return ProgressOut(**running.snapshot())

    session = await service.session(scan_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No scan {scan_id!r}.")
    completed, total, percent = progress_counts(session)
    return ProgressOut(
        scan_id=session.id,
        state=session.state.value,
        completed=completed,
        total=total,
        percent=percent,
    )


@router.post("/{scan_id}/cancel", response_model=ProgressOut, summary="Cancel a running scan")
async def cancel_scan(scan_id: str, service: Service) -> ProgressOut:
    if not await service.cancel(scan_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Scan {scan_id!r} is not running.",
        )
    running = service.running(scan_id)
    assert running is not None  # nosec B101 - cancel() returned True, so it exists
    return ProgressOut(**running.snapshot())


@router.get("/{scan_id}/logs", response_model=LogList, summary="Scan log lines")
async def scan_logs(
    scan_id: str, service: Service, limit: int = Query(200, ge=1, le=2000)
) -> LogList:
    """The per-plugin log the Scan Center and Scan History log panes display.

    WHY THIS EXISTS SEPARATELY FROM ``/events``
        ``/events`` is a live SSE stream and 404s the moment a scan finishes -- by design, it is for
        watching a run in progress. The dashboard's log pane, however, is shown for FINISHED scans
        too, and it has always called ``GET /scans/{id}/logs``, which was never implemented. The
        service layer swallows the resulting "not implemented" and returns an empty list, so the
        pane rendered blank for every scan ever run and looked like a dead feature rather than a
        missing route.

    WHERE THE LINES COME FROM
        The stored ``plugin_results`` rows, one line per plugin. That is the durable record of what
        the scan actually did; reconstructing it from the process log file would tie the API to a
        file on the engine's disk, which the dashboard may not share.

    Severity maps from outcome so the pane can colour lines: a FAIL is a finding (WARNING), an ERROR
    is machinery breaking (ERROR), a SKIP is a coverage gap worth seeing but not alarming (DEBUG).
    """
    session = await service.session(scan_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No scan {scan_id!r}.")

    results = await service.results(scan_id)
    lines: list[LogLineOut] = [
        LogLineOut(
            timestamp=session.started_at.isoformat() if session.started_at else "",
            level="INFO",
            source="scan",
            message=(
                f"scan started against {session.target_name!r} "
                f"({session.plugins_total} plugins planned)"
            ),
        )
    ]
    for result in sorted(results, key=lambda r: r.created_at):
        lines.append(
            LogLineOut(
                timestamp=result.created_at.isoformat() if result.created_at else "",
                level=_LOG_LEVEL_FOR.get(result.outcome, "INFO"),
                source=result.plugin_slug,
                message=(
                    f"{result.outcome.value}: {result.summary or result.detail or 'no detail'}"
                    + (f" ({result.elapsed_ms} ms)" if result.elapsed_ms else "")
                    + (f" -- {result.error}" if result.error else "")
                ),
            )
        )
    if session.finished_at:
        lines.append(
            LogLineOut(
                timestamp=session.finished_at.isoformat(),
                level="INFO",
                source="scan",
                message=(
                    f"scan {session.state.value.lower()} -- "
                    f"{session.plugins_failed} failed, {session.plugins_errored} errored, "
                    f"{session.plugins_skipped} skipped, coverage {session.coverage:.0%}"
                ),
            )
        )
    # Newest lines matter most when truncating, so keep the tail rather than the head.
    return LogList(lines=lines[-limit:])


@router.get("/{scan_id}/findings", response_model=FindingList, summary="Findings for a scan")
async def scan_findings(scan_id: str, service: Service) -> FindingList:
    session = await service.session(scan_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No scan {scan_id!r}.")

    findings = await service.findings.findings_for(scan_id)
    return FindingList(
        findings=[
            FindingOut(
                finding_id=finding.id,
                plugin=finding.plugin_id,
                category=finding.category,
                status=finding.status.value,
                severity=finding.severity.value,
                confidence=round(finding.confidence, 4),
                risk_score=round(finding.risk_score, 2),
                # `Finding` has no free-text description; `notes` is the analyzer's
                # trace of which rules fired, which is the useful thing to surface.
                description=finding.notes,
                recommendation=finding.recommendation,
            )
            for finding in findings
        ],
        # Coverage travels with the findings, always. A list of zero findings from a scan that ran
        # 40% of its packs is a different statement from zero out of all of them (ADR-020).
        coverage=round(session.coverage, 4),
    )
