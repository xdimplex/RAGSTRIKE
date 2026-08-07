"""Targets: list, inspect, create, edit, delete, verify.

WHAT THIS SERVICE DELIBERATELY DOES NOT DO
    It does not decide whether a target is in scope. Scope enforcement lives in
    ``target_adapters.build_adapter`` on the engine side, where every call path -- scan, verify, CLI
    -- passes through it and none can skip it. A second implementation here would be a second
    opinion, and the failure mode of two opinions about "is this host allowed" is that the permissive
    one wins by accident.

    What it *does* do is refuse to submit an obviously non-local target without the operator having
    seen the warning. That is a UI affordance layered on top of the real guard, not a replacement
    for it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ragstrike.dashboard.services.models import TargetHealth, TargetView
from ragstrike.dashboard.services.transport import BackendTransport

#: Hosts the framework treats as local by default. Mirrors ``safety.allowed_hosts`` in the shipped
#: config. Used only to phrase a warning; see the module docstring.
#:
#: The ``0.0.0.0`` entry is a *pattern to recognise*, not an address to bind -- this module opens no
#: socket. Both linters flag it as a bind-all, hence the two suppressions.
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1", "0.0.0.0")  # noqa: S104  # nosec B104


def looks_local(url: str) -> bool:
    lowered = url.strip().lower()
    return any(f"//{host}" in lowered or f"//[{host}]" in lowered for host in LOCAL_HOSTS)


@dataclass(frozen=True, slots=True)
class TargetService:
    """Everything the Targets page needs, and nothing a page should be doing itself."""

    transport: BackendTransport

    def list_targets(self) -> list[TargetView]:
        payload = self.transport.request("GET", "/targets")
        rows = payload.get("targets", []) if isinstance(payload, Mapping) else []
        return [TargetView.from_payload(row) for row in rows if isinstance(row, Mapping)]

    def get_target(self, target_id: str) -> TargetView:
        payload = self.transport.request("GET", f"/targets/{target_id}")
        return TargetView.from_payload(payload if isinstance(payload, Mapping) else {})

    def create_target(self, fields: Mapping[str, Any]) -> TargetView:
        payload = self.transport.request("POST", "/targets", json=dict(fields))
        return TargetView.from_payload(payload if isinstance(payload, Mapping) else {})

    def update_target(self, target_id: str, fields: Mapping[str, Any]) -> TargetView:
        payload = self.transport.request("PATCH", f"/targets/{target_id}", json=dict(fields))
        return TargetView.from_payload(payload if isinstance(payload, Mapping) else {})

    def delete_target(self, target_id: str) -> None:
        self.transport.request("DELETE", f"/targets/{target_id}")

    def test_connection(self, target_id: str) -> TargetHealth:
        """Probe one target. The backend performs the probe; the dashboard never opens a socket to
        a scan target itself -- that would be network egress from the UI process, which ADR-010's
        separation exists to prevent."""
        payload = self.transport.request("POST", f"/targets/{target_id}/verify")
        return TargetHealth.from_payload(payload if isinstance(payload, Mapping) else {})

    def names(self) -> list[str]:
        """Target names for a select box, enabled ones first."""
        targets = self.list_targets()
        return [t.name for t in targets if t.enabled] + [t.name for t in targets if not t.enabled]
