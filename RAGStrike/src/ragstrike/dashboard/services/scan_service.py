"""Scans: plan, start, watch, cancel.

LIVE UPDATES ARE POLLED, NOT STREAMED
    ADR-014 chose SSE for progress, and SSE is the right transport for a browser. Streamlit is not a
    browser client here -- the Python process is the client, and it re-runs the whole script on a
    timer anyway. So this service exposes a single ``progress()`` call and the page re-asks on the
    configured interval. The brief says the same thing in one line: "Use polling architecture. Do not
    implement WebSockets yet."

    :func:`should_poll` is where the loop stops. A poller that keeps asking after a scan has finished
    is a busy loop against the backend that nobody notices until it is running on a laptop for eight
    hours.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ragstrike.dashboard.services.errors import DashboardError, NotImplementedByBackendError
from ragstrike.dashboard.services.models import (
    TERMINAL_STATES,
    FindingView,
    LogLine,
    ScanProgress,
    ScanView,
    as_int,
    as_str,
)
from ragstrike.dashboard.services.transport import BackendTransport


@dataclass(frozen=True, slots=True)
class ScanProfile:
    """A named scan configuration offered by the backend."""

    id: str
    name: str = ""
    description: str = ""
    estimated_cases: int = 0

    @property
    def label(self) -> str:
        return self.name or self.id.title()


@dataclass(frozen=True, slots=True)
class ScanRequest:
    """What the operator assembled on the Scan Center page.

    ``authorized`` is **not** permission -- the backend holds a persisted authorization record per
    target and enforces it regardless of anything sent here. It is the operator confirming, in this
    request, that they meant to start this scan.

    It is sent. It did not used to be, on the reasoning that the backend enforces target
    authorization on its own. That reasoning was right about the *target* record and wrong about the
    *request*: ``POST /scans`` has a separate per-request confirmation gate, so omitting this made
    every Start Scan click a 400 the moment the API existed to answer it.
    """

    target: str
    profile: str = "standard"
    name: str = ""
    plugins: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    authorized: bool = False

    @property
    def ready(self) -> bool:
        return bool(self.target) and self.authorized

    def payload(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "target": self.target,
            "profile": self.profile,
            "authorized": self.authorized,
        }
        if self.name:
            body["name"] = self.name
        if self.plugins:
            body["plugins"] = list(self.plugins)
        if self.categories:
            body["categories"] = list(self.categories)
        return body


def should_poll(state: str) -> bool:
    """Whether a scan in this state is still worth asking about."""
    return state.strip().lower() not in TERMINAL_STATES


@dataclass(frozen=True, slots=True)
class ScanService:
    """The Scan Center's only route to the engine."""

    transport: BackendTransport

    # -- planning ---------------------------------------------------------------------------------

    def profiles(self) -> list[ScanProfile]:
        """Scan profiles. Falls back to the three the repository ships when the backend has no
        ``/profiles`` route, so the page is usable against an older API."""
        try:
            payload = self.transport.request("GET", "/profiles")
        except NotImplementedByBackendError:
            return [
                ScanProfile(id="quick", name="Quick", description="Smoke coverage."),
                ScanProfile(id="standard", name="Standard", description="The default."),
                ScanProfile(id="deep", name="Deep", description="Full payload sets."),
            ]
        rows = payload.get("profiles", []) if isinstance(payload, Mapping) else []
        return [
            ScanProfile(
                id=as_str(row, "id"),
                name=as_str(row, "name"),
                description=as_str(row, "description"),
                estimated_cases=as_int(row, "estimated_cases"),
            )
            for row in rows
            if isinstance(row, Mapping)
        ]

    # -- control ----------------------------------------------------------------------------------

    def start(self, request: ScanRequest) -> str:
        """Start a scan and return its id.

        Refuses locally when the authorization box is unticked. That is a second gate in front of
        the backend's own -- deliberately redundant, because the cost of the redundancy is one
        boolean and the cost of missing it is scanning something nobody agreed to scan.
        """
        if not request.authorized:
            raise DashboardError(
                "Confirm you are authorized to test this target before starting a scan."
            )
        payload = self.transport.request("POST", "/scans", json=request.payload())
        # The backend returns the identifier under both `id` and `scan_id`. Reading both means a
        # server that emits only one of them still works -- which is the failure this line hit.
        scan_id = ""
        if isinstance(payload, Mapping):
            scan_id = as_str(payload, "id") or as_str(payload, "scan_id")
        if not scan_id:
            raise DashboardError("The backend accepted the scan but returned no scan id.")
        return scan_id

    def cancel(self, scan_id: str) -> ScanView:
        payload = self.transport.request("POST", f"/scans/{scan_id}/cancel")
        return ScanView.from_payload(payload if isinstance(payload, Mapping) else {})

    # -- observation ------------------------------------------------------------------------------

    def detail(self, scan_id: str) -> ScanView:
        payload = self.transport.request("GET", f"/scans/{scan_id}")
        return ScanView.from_payload(payload if isinstance(payload, Mapping) else {})

    def progress(self, scan_id: str) -> ScanProgress:
        """One poll.

        A backend without a ``/progress`` route degrades to the scan record itself, so the page
        still shows state and counts -- just without a live stage. Better than an error banner on a
        scan that is running perfectly well.
        """
        try:
            payload = self.transport.request("GET", f"/scans/{scan_id}/progress")
        except NotImplementedByBackendError:
            scan = self.detail(scan_id)
            return ScanProgress(
                scan_id=scan_id,
                state=scan.state,
                completed=scan.findings_count,
                total=scan.findings_count,
                current_stage="",
                findings_so_far=scan.findings_count,
            )
        return ScanProgress.from_payload(payload if isinstance(payload, Mapping) else {})

    def findings(self, scan_id: str, *, severity: str = "") -> list[FindingView]:
        params = {"severity": severity} if severity else None
        payload = self.transport.request("GET", f"/scans/{scan_id}/findings", params=params)
        rows = payload.get("findings", []) if isinstance(payload, Mapping) else []
        return [FindingView.from_payload(row) for row in rows if isinstance(row, Mapping)]

    def logs(self, scan_id: str, *, limit: int = 200) -> list[LogLine]:
        """Scan log lines for the log viewer.

        Returns an empty list rather than raising when the backend has no log route -- a missing log
        pane should not take down the progress view it sits next to.
        """
        try:
            payload = self.transport.request(
                "GET", f"/scans/{scan_id}/logs", params={"limit": limit}
            )
        except NotImplementedByBackendError:
            return []
        rows = payload.get("lines", []) if isinstance(payload, Mapping) else []
        lines = [LogLine.from_payload(row) for row in rows if isinstance(row, Mapping)]
        return lines[-limit:]

    def estimate(self, profile: ScanProfile, plugin_count: int) -> tuple[int, float]:
        """Cases and seconds, estimated for the plan summary.

        Arithmetic, not a prediction: cases scale with the selected plugins, and the per-case figure
        is a fixed constant shown as "estimated" in the UI. A number derived from something the
        operator can see beats a confident-looking number derived from nothing.
        """
        per_plugin = max(1, profile.estimated_cases // 8) if profile.estimated_cases else 40
        cases = per_plugin * max(1, plugin_count)
        return cases, cases * 0.55


def profile_ids(profiles: Sequence[ScanProfile]) -> list[str]:
    return [profile.id for profile in profiles]
