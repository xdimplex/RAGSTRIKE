"""Report generation and download.

WHY GENERATION IS SYNCHRONOUS WHEN SCANNING IS NOT
    Rendering is arithmetic over findings already in the database -- milliseconds, no model calls,
    no network. The asynchrony that a scan needs would be pure ceremony here.

WHY A FORMAT THAT CANNOT RENDER IS A 400 AND NOT A 500
    Asking for a format the engine does not have is a client mistake with an obvious fix, and the
    response names the formats that do work. Returning 500 would imply the server broke.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from ragstrike import __version__
from ragstrike.api.deps import get_service
from ragstrike.api.routers.scans import _grade
from ragstrike.api.schemas.models import (
    ReportList,
    ReportOut,
    ReportRequest,
    ReportSummaryOut,
)
from ragstrike.api.service import ScanService
from ragstrike.reporters.base.record import StoredReport
from ragstrike.reporters.config import build_service as build_reporting
from ragstrike.reporters.exporters.export_manager import ExportManager, safe_component

router = APIRouter(tags=["reports"])

Service = Annotated[ScanService, Depends(get_service)]

#: Content types for the stored-report endpoint. Kept beside the routes that use them rather than
#: imported from the dashboard, which must not be a dependency of the API.
MEDIA_TYPES: dict[str, str] = {
    "html": "text/html",
    "json": "application/json",
    "markdown": "text/markdown",
    "pdf": "application/pdf",
}

#: Formats whose stored ``content`` is base64 rather than the document itself.
BINARY_FORMATS: frozenset[str] = frozenset({"pdf"})


@router.post(
    "/scans/{scan_id}/reports",
    response_model=ReportOut,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a report for a scan",
)
async def generate_report(scan_id: str, request: ReportRequest, service: Service) -> ReportOut:
    session = await service.session(scan_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No scan {scan_id!r}.")

    reporting, config, _ = build_reporting()
    wanted = request.chosen()
    available = reporting.engine.formats()
    unavailable = [fmt for fmt in wanted if not available.get(fmt)]
    if unavailable:
        working = ", ".join(sorted(name for name, ok in available.items() if ok))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot render {', '.join(unavailable)}. Available formats: {working}.",
        )

    findings = await service.findings.findings_for(scan_id)

    # Pass the scan's own facts into the report context.
    #
    # This used to be `config.context(scan_id=scan_id)` and nothing else, so every generated report
    # said `Target: unknown`, `Framework: unknown`, and `Duration: 0ms` -- while its own statistics
    # section, computed from the findings, showed the real elapsed time. A report that contradicts
    # itself on the first page is not evidence, and "unknown" target on a security assessment is the
    # single most important field to get right.
    duration_ms = 0
    if session.finished_at and session.started_at:
        duration_ms = int((session.finished_at - session.started_at).total_seconds() * 1000)

    generated = reporting.generate(
        findings,
        config.context(
            scan_id=scan_id,
            target=session.target_name,
            framework_version=__version__,
            analyzer_version="1.0.0",
            scoring_model_version="1.0.0",
            duration_ms=duration_ms,
            scan_started=session.started_at,
            scan_finished=session.finished_at,
            scan_score=round(max((f.risk_score for f in findings), default=0.0), 2),
        ),
    )

    # FOLDER AND FILENAME CARRY THE SCAN'S NAME, NOT ITS ID.
    #
    # `reports/47cce83d3e9f4512a327b7409e2f4859/ragstrike-47cce83d....html` is unusable: a directory
    # listing of a dozen scans is a wall of identical-looking hex, and an operator who wants "the
    # standard run against secure-rag" has to open them one by one to find it.
    #
    # `safe_component` is doing security work, not tidying. The name is operator-supplied text going
    # into a filesystem path, so directory separators and parent references have to come out --
    # `../../etc/foo` as a scan name must not escape the reports directory.
    #
    # The id is APPENDED rather than replaced. Two scans may legitimately share a name ("nightly
    # sweep" run twice), and a report that silently overwrote yesterday's would lose evidence; the
    # suffix keeps them distinct while the readable part stays in front.
    label = safe_component(session.display_name, fallback=scan_id)
    folder = f"{label}-{scan_id[:8]}"

    output_dir = service.settings.storage.reports_dir / folder
    manager = ExportManager(reporting.engine, output_dir)
    written = {
        fmt: str(
            manager.export(generated, fmt, filename=f"{label}-{scan_id[:8]}.{fmt}").path
        )
        for fmt in wanted
    }

    # Record it. Rendering used to write files and stop there, so `GET /reports` had nothing to
    # return and the Reports page stayed empty however many times an operator pressed Generate --
    # the button worked, and produced no visible effect anywhere in the UI.
    #
    # The rendered content is stored, not just the path: the file lives on the ENGINE's filesystem,
    # which in the shipped compose file is a different container from the dashboard, so a path alone
    # is not something the browser can ever open.
    for fmt in wanted:
        await service.reports.save_report(
            StoredReport(
                id=f"{generated.model.report_id}-{fmt}",
                scan_id=scan_id,
                title=f"RAG Security Assessment — {session.target_name or scan_id}",
                target=session.target_name,
                fmt=fmt,
                content=_stored_content(reporting.engine, generated, fmt),
                summary={
                    "coverage": round(session.coverage, 4),
                    "plugins_executed": session.plugins_executed,
                    "plugins_failed": session.plugins_failed,
                    "plugins_skipped": session.plugins_skipped,
                },
                finding_count=len(findings),
                risk_score=round(max((f.risk_score for f in findings), default=0.0), 2),
                status=session.state.value,
                analyzer_version="1.0.0",
                framework_version=__version__,
                generated_at=generated.model.cover.generated_at,
            )
        )

    return ReportOut(
        report_id=generated.model.report_id,
        scan_id=scan_id,
        generated_at=generated.model.cover.generated_at,
        formats=written,
    )


async def _render_html(scan_id: str, directory: Path, service: ScanService) -> Path | None:
    """Render this scan's report as HTML into *directory*, returning the file.

    ``None`` when the scan itself is gone -- the caller turns that into the same 404 it would have
    raised anyway. Only HTML is produced here; every other format keeps "generate it explicitly"
    semantics, because only HTML has a caller that needs it to exist unconditionally.
    """
    session = await service.session(scan_id)
    if session is None:
        return None

    findings = await service.findings.findings_for(scan_id)
    reporting, config, _ = build_reporting()
    duration_ms = 0
    if session.finished_at and session.started_at:
        duration_ms = int((session.finished_at - session.started_at).total_seconds() * 1000)

    generated = reporting.generate(
        findings,
        config.context(
            scan_id=scan_id,
            target=session.target_name,
            framework_version=__version__,
            analyzer_version="1.0.0",
            scoring_model_version="1.0.0",
            duration_ms=duration_ms,
            scan_started=session.started_at,
            scan_finished=session.finished_at,
            scan_score=round(max((f.risk_score for f in findings), default=0.0), 2),
        ),
    )
    label = safe_component(session.display_name, fallback=scan_id)
    manager = ExportManager(reporting.engine, directory)
    return Path(manager.export(generated, "html", filename=f"{label}-{scan_id[:8]}.html").path)


def _stored_content(engine: Any, generated: Any, fmt: str) -> str:
    """The document to persist, as text.

    A binary renderer's ``render()`` is NOT the document. PDF's returns a one-line note saying
    "binary output; use render_bytes()", so persisting it stored a 121-byte apology in place of a
    seven-kilobyte report -- and the Reports page dutifully displayed "121 B" next to it.

    Binary formats are therefore base64-encoded into the text column. The alternative, storing only
    a filesystem path, breaks the moment the dashboard and the engine are different containers,
    which is exactly how the shipped compose file runs them.
    """
    if engine.is_binary(fmt):
        return base64.b64encode(engine.render_bytes(generated, fmt)).decode("ascii")
    return str(engine.render(generated, fmt))


@router.get("/reports", response_model=ReportList, summary="Every stored report")
async def list_reports(service: Service, scan_id: str = "") -> ReportList:
    """The report history the Reports page lists.

    Metadata only -- ``content`` is deliberately excluded. A listing that carried every rendered
    document would ship megabytes to draw a table of a dozen rows.
    """
    records = await service.reports.list_reports(scan_id)

    # SCAN NAMES, RESOLVED ONCE PER DISTINCT SCAN.
    #
    # A report is identified in the UI by the scan it covers, and a scan is identified by its name.
    # The stored report carries only `scan_id`, so the name is looked up here -- once per scan, not
    # once per report, because a scan commonly has an HTML and a PDF report and several regenerated
    # copies of each.
    #
    # Resolved at listing time rather than denormalised onto the report record: every report already
    # in the database predates this field, and a stored copy would leave those permanently nameless
    # while also going stale if a scan were ever renamed.
    #
    # The grade rides along on the same lookup. It is `_grade` from the scans router rather than a
    # second threshold table written here: two implementations of "what letter is this risk" would
    # eventually disagree, and the Reports page would then contradict Scan History about the very
    # same scan. `measured=True` is honest -- a stored report was rendered FROM findings, so they
    # were loaded by definition.
    names: dict[str, str] = {}
    grades: dict[str, str] = {}
    for record in records:
        if record.scan_id in names:
            continue
        session = await service.session(record.scan_id)
        names[record.scan_id] = session.display_name if session else ""
        grades[record.scan_id] = (
            _grade(record.finding_count, record.risk_score, session, measured=True)
            if session
            else ""
        )

    return ReportList(
        reports=[
            ReportSummaryOut(
                report_id=record.id,
                scan_id=record.scan_id,
                scan_name=names.get(record.scan_id, ""),
                title=record.title,
                target=record.target,
                format=record.fmt,
                finding_count=record.finding_count,
                risk_score=record.risk_score,
                grade=grades.get(record.scan_id, ""),
                status=record.status,
                size_bytes=record.size_bytes,
                generated_at=record.generated_at,
            )
            for record in records
        ]
    )


@router.get(
    "/scans/{scan_id}/reports/id/{report_id}",
    summary="Open one stored report by id",
)
async def open_report(scan_id: str, report_id: str, service: Service) -> dict[str, str]:
    """Return a stored report's rendered body, for display or download in the browser.

    Distinct from the ``/{fmt}`` route below, which serves the file from disk. This one serves the
    bytes that were recorded at generation time, which is what an audit means by "the report" -- a
    re-render could differ the moment a template changes.

    The path segment is ``/id/{report_id}`` rather than ``/{report_id}`` so it cannot be confused
    with a format name by either FastAPI or a reader.
    """
    record = await service.reports.load_report(report_id)
    if record is None or record.scan_id != scan_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No report {report_id!r} for scan {scan_id!r}.",
        )
    # `encoding` is explicit so a client never has to guess whether it is holding text or base64.
    # Guessing by format would put the rule in two places and let them disagree.
    return {
        "report_id": record.id,
        "scan_id": record.scan_id,
        "format": record.fmt,
        "content": record.content,
        "media_type": MEDIA_TYPES.get(record.fmt, "text/plain"),
        "encoding": "base64" if record.fmt in BINARY_FORMATS else "text",
    }


@router.delete(
    "/reports/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a stored report",
)
async def delete_report(report_id: str, service: Service) -> None:
    if not await service.reports.delete_report(report_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"No report {report_id!r}."
        )


@router.get(
    "/scans/{scan_id}/reports/{fmt}",
    response_class=FileResponse,
    summary="Download a generated report",
)
async def download_report(
    scan_id: str,
    fmt: str,
    service: Service,
    inline: Annotated[bool, Query()] = False,
) -> FileResponse:
    """Serve a previously generated report file.

    Both path segments are used to build a filesystem path, so both are constrained: ``fmt`` must be
    a known format, and the resolved path must sit inside the reports directory. ``../`` in a URL
    reaching a file read is the oldest bug there is, and this is a security tool.

    ``inline=true`` drops the ``Content-Disposition: attachment`` header so a browser renders the
    report in a tab instead of downloading it. The dashboard links to this so "Open report" opens a
    real, full-window page -- it used to render into a 720px sandboxed frame inside the page, which
    is safe but reads as a cramped preview of a document rather than the document.

    WHY SERVING IT INLINE IS ACCEPTABLE HERE
        A report is built from target responses, which is to say from text an attacker influenced.
        Splicing that into the dashboard's DOM would make the report an XSS vector against the tool
        that produced it -- which is why the in-page preview is sandboxed and stays that way.

        This route is a different origin from the dashboard (the API is on its own port), so a script
        in a report cannot reach the dashboard's DOM or storage. The API holds no cookie or session
        for it to steal either: authorization here is a per-target record, not a browser credential.
    """
    reporting, _, _ = build_reporting()
    if fmt not in reporting.engine.formats():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown format {fmt!r}."
        )

    root = service.settings.storage.reports_dir.resolve()

    # Report folders are named `{scan-name}-{scan_id[:8]}`, not `{scan_id}`, so the folder cannot be
    # derived from the id alone -- it is found by its id suffix. The older `{scan_id}` layout is
    # still matched, because reports generated before that change are still on disk and an operator
    # opening a week-old assessment should not get a 404.
    candidates = [
        d
        for d in (root / scan_id, *sorted(root.glob(f"*-{scan_id[:8]}")))
        if d.is_dir() and d.resolve().is_relative_to(root)
    ]
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No reports for scan {scan_id!r}. Generate one first.",
        )
    directory = candidates[-1]

    matches = sorted(directory.glob(f"*.{fmt}"))

    # HTML IS RENDERED ON DEMAND WHEN IT IS MISSING.
    #
    # The dashboard's preview link always asks for HTML, because HTML is the only format a browser
    # renders as a document in a tab -- a PDF preview depends on the browser's plugin, and Markdown
    # and JSON display as source. A report generated only as PDF therefore has no HTML file, and the
    # preview link for it used to 404 in a fresh tab.
    #
    # Re-rendering is safe and cheap: a report is a deterministic render over findings already in
    # the database, so the HTML produced here is the same document the PDF was made from. It is
    # written into the scan's own report folder so the next request is a plain file read.
    if not matches and fmt == "html":
        rendered = await _render_html(scan_id, directory, service)
        matches = [rendered] if rendered else []

    if not matches:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {fmt} report for scan {scan_id!r}. Generate one first.",
        )
    path = _within(matches[0], root)
    if inline:
        # No `filename=`: that is what sets Content-Disposition: attachment. Without it the browser
        # renders the file, which is the whole point of the inline mode.
        return FileResponse(path, media_type=_INLINE_MEDIA.get(fmt, "text/plain"))
    return FileResponse(path, filename=matches[0].name)


#: Media types for inline display. Only formats a browser can render usefully appear here; anything
#: else falls back to text/plain rather than inviting the browser to guess.
_INLINE_MEDIA = {
    "html": "text/html",
    "markdown": "text/plain; charset=utf-8",
    "json": "application/json",
}


def _within(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root):  # pragma: no cover - defensive
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid report path.")
    return resolved
