"""Reports: list, open, generate, export, delete.

WHAT "EXPORT" MEANS HERE
    The reporting engine (Phase 11) writes files on the *engine's* filesystem. The dashboard may be
    running in a different container, so "export" in the UI means "ask the backend to render, then
    hand the bytes to the browser as a download". The dashboard never writes a report to disk itself
    -- it has no business owning a path on a machine the operator may not even be sitting at.

FORMATS
    The available set comes from the backend's ``/version`` response, not from a constant here. PDF
    ships as a declared placeholder in Phase 11: it is *listed* and *not available*, and the UI shows
    it disabled with that reason rather than hiding it. A missing option looks like a bug; a disabled
    one with a reason is information.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ragstrike.dashboard.services.errors import NotImplementedByBackendError, ReportFailureError
from ragstrike.dashboard.services.models import ReportView, as_bool
from ragstrike.dashboard.services.transport import BackendTransport


@dataclass(frozen=True, slots=True)
class RenderedReport:
    """A report's bytes plus what a download button needs to offer it."""

    report_id: str
    fmt: str
    content: str
    media_type: str = "text/plain"
    #: ``"base64"`` when ``content`` encodes a binary document (PDF). The backend states this
    #: explicitly rather than leaving the client to infer it from the format name -- inferring it
    #: would put the rule in two places and let them drift.
    encoding: str = "text"

    @property
    def filename(self) -> str:
        return f"{self.report_id or 'report'}.{self.fmt}"

    @property
    def data(self) -> bytes:
        """The document as bytes, ready for a download button, whatever the transport encoding."""
        if self.encoding == "base64":
            return base64.b64decode(self.content)
        return self.content.encode("utf-8")

    @property
    def is_binary(self) -> bool:
        """Whether this can be shown inline. A PDF cannot be pasted into a text area."""
        return self.encoding == "base64"


#: Fallback media types, used when the backend does not send one.
MEDIA_TYPES: dict[str, str] = {
    "html": "text/html",
    "json": "application/json",
    "markdown": "text/markdown",
    "pdf": "application/pdf",
}


@dataclass(frozen=True, slots=True)
class ReportService:
    """The Reports page's only route to the engine."""

    transport: BackendTransport

    def list_reports(self) -> list[ReportView]:
        """Every stored report.

        Returns an empty list when the backend has no cross-scan listing, because "no reports yet"
        and "this API cannot list reports" look identical to an operator and the empty state already
        explains what to do next.
        """
        try:
            payload = self.transport.request("GET", "/reports")
        except NotImplementedByBackendError:
            return []
        rows = payload.get("reports", []) if isinstance(payload, Mapping) else []
        return [ReportView.from_payload(row) for row in rows if isinstance(row, Mapping)]

    def formats(self) -> dict[str, bool]:
        """Format name to "can actually render". Mirrors ``ReportEngine.formats()``."""
        try:
            payload = self.transport.request("GET", "/version")
        except NotImplementedByBackendError:
            return {}
        raw = payload.get("report_formats") if isinstance(payload, Mapping) else None
        if not isinstance(raw, Mapping):
            return {}
        return {str(name): as_bool(raw, str(name)) for name in raw}

    def generate(self, scan_id: str, fmt: str, **options: Any) -> ReportView:
        available = self.formats()
        if available and not available.get(fmt, True):
            raise ReportFailureError(
                f"The backend lists {fmt} but cannot render it yet.",
                detail="PDF is a declared placeholder in the reporting engine.",
            )
        payload = self.transport.request(
            "POST", f"/scans/{scan_id}/reports", json={"format": fmt, **options}
        )
        return ReportView.from_payload(payload if isinstance(payload, Mapping) else {})

    def inline_url(self, scan_id: str, fmt: str) -> str:
        """A browsable URL for a stored report, or ``""`` when there is nothing to link to.

        Points at the API rather than the dashboard on purpose. A report is rendered from target
        responses -- attacker-influenced text -- so it must not be served from the dashboard's own
        origin; the API is a separate origin holding no cookie or session for a script in a report
        to reach.

        Empty for the demo transport, which has no HTTP endpoint behind it: a dead link is worse
        than an absent one.
        """
        base = getattr(self.transport, "base_url", "")
        if not base or not scan_id:
            return ""
        return f"{base}/scans/{scan_id}/reports/{fmt}?inline=true"

    def open_report(self, scan_id: str, report_id: str, fmt: str) -> RenderedReport:
        """Fetch a rendered report for display or download.

        The ``/id/`` segment is not decoration. ``/scans/{id}/reports/{fmt}`` already serves the
        newest file of a given format from disk, so without it a report id would be parsed as a
        format name and rejected as unknown.
        """
        payload = self.transport.request("GET", f"/scans/{scan_id}/reports/id/{report_id}")
        if isinstance(payload, Mapping):
            content = str(payload.get("content", ""))
            media = str(payload.get("media_type", "")) or MEDIA_TYPES.get(fmt, "text/plain")
            encoding = str(payload.get("encoding", "")) or "text"
        else:
            content = str(payload or "")
            media = MEDIA_TYPES.get(fmt, "text/plain")
            encoding = "text"
        if not content:
            raise ReportFailureError("The backend returned an empty report body.")
        return RenderedReport(
            report_id=report_id,
            fmt=fmt,
            content=content,
            media_type=media,
            encoding=encoding,
        )

    def delete_report(self, report_id: str) -> None:
        self.transport.request("DELETE", f"/reports/{report_id}")
