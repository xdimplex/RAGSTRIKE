"""Scan history: list, detail, compare, replay.

WHY COMPARISON IS A BACKEND CALL AND NOT A DIFF IN THE UI
    Diffing two scans looks like set arithmetic on finding titles, and it is not: whether a finding
    "persists" depends on identity rules the analyzer owns, and comparing across scoring-model
    versions is refused rather than approximated (ADR-011). Doing it here would produce a second,
    subtly wrong answer that renders in exactly the same table as the right one.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ragstrike.dashboard.services.errors import NotImplementedByBackendError
from ragstrike.dashboard.services.models import ScanView, as_list
from ragstrike.dashboard.services.transport import BackendTransport


@dataclass(frozen=True, slots=True)
class ScanComparison:
    """A posture delta between two scans."""

    base: ScanView
    head: ScanView
    new: tuple[str, ...] = ()
    fixed: tuple[str, ...] = ()
    persisting: tuple[str, ...] = ()
    comparable: bool = True
    reason: str = ""

    @property
    def risk_delta(self) -> float:
        return self.head.risk_score - self.base.risk_score


@dataclass(frozen=True, slots=True)
class HistoryService:
    """The Scan History page's only route to the engine."""

    transport: BackendTransport

    def list_scans(self, *, target: str = "") -> list[ScanView]:
        params = {"target": target} if target else None
        payload = self.transport.request("GET", "/scans", params=params)
        rows = payload.get("scans", []) if isinstance(payload, Mapping) else []
        scans = [ScanView.from_payload(row) for row in rows if isinstance(row, Mapping)]
        # Newest first, and stable for scans that share a timestamp -- an unstable order makes a
        # history table appear to shuffle on every poll.
        return sorted(scans, key=lambda scan: scan.started_at, reverse=True)

    def detail(self, scan_id: str) -> ScanView:
        payload = self.transport.request("GET", f"/scans/{scan_id}")
        return ScanView.from_payload(payload if isinstance(payload, Mapping) else {})

    def compare(self, base_id: str, head_id: str) -> ScanComparison:
        try:
            payload = self.transport.request(
                "GET", "/scans/compare", params={"base": base_id, "head": head_id}
            )
        except NotImplementedByBackendError:
            return ScanComparison(
                base=self.detail(base_id),
                head=self.detail(head_id),
                comparable=False,
                reason="The backend does not expose scan comparison yet.",
            )
        body: Mapping[str, object] = payload if isinstance(payload, Mapping) else {}
        base_raw = body.get("base")
        head_raw = body.get("head")
        return ScanComparison(
            base=ScanView.from_payload(base_raw if isinstance(base_raw, Mapping) else {}),
            head=ScanView.from_payload(head_raw if isinstance(head_raw, Mapping) else {}),
            new=tuple(as_list(body, "new")),
            fixed=tuple(as_list(body, "fixed")),
            persisting=tuple(as_list(body, "persisting")),
        )

    def targets_seen(self) -> list[str]:
        """Distinct targets in the history, for the comparison selectors."""
        return sorted({scan.target for scan in self.list_scans() if scan.target})

    def trend(self, target: str, *, limit: int = 10) -> list[tuple[str, float]]:
        """(timestamp, risk score) for the last N scans of one target, oldest first.

        Oldest first because a trend line is read left to right; the list endpoint returns newest
        first because a table is read top down. The reversal happens here so no chart has to
        remember to do it.
        """
        scans = [s for s in self.list_scans(target=target) if s.finished][:limit]
        return [(scan.started_at, scan.risk_score) for scan in reversed(scans)]
