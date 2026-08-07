"""Plugins: inventory, enable/disable, reload, validate, metadata.

THE LINE THIS SERVICE HOLDS
    The brief says "Do not edit plugin code", and nothing here can: every operation is a state
    change the *backend* performs against ``configs/plugins.yaml`` through the PluginManager, which
    is the single place plugin state is mutated in the whole system. The dashboard names a slug and
    an action; it never touches a file.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ragstrike.dashboard.services.models import PluginView, as_bool, as_str
from ragstrike.dashboard.services.transport import BackendTransport


@dataclass(frozen=True, slots=True)
class ValidationCheck:
    """One rule's verdict from ``plugins validate``."""

    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """The full validation result for one plugin."""

    slug: str
    valid: bool
    checks: tuple[ValidationCheck, ...] = ()

    @property
    def failures(self) -> tuple[ValidationCheck, ...]:
        return tuple(check for check in self.checks if not check.passed)


@dataclass(frozen=True, slots=True)
class PluginInventory:
    """The whole installed set, split the way the engine splits it.

    ``rejected`` is not an error state to hide: a plugin refused for requesting elevated permissions
    is the framework working, and the operator needs to see the reason.
    """

    active: tuple[PluginView, ...] = ()
    rejected: tuple[PluginView, ...] = ()

    @property
    def all(self) -> tuple[PluginView, ...]:
        return self.active + self.rejected

    @property
    def categories(self) -> tuple[str, ...]:
        return tuple(sorted({p.category for p in self.all if p.category}))

    def by_category(self, category: str) -> tuple[PluginView, ...]:
        return tuple(p for p in self.all if p.category == category)

    def enabled_slugs(self) -> tuple[str, ...]:
        return tuple(p.slug for p in self.active if p.enabled)


@dataclass(frozen=True, slots=True)
class PluginService:
    """The Plugins page's only route to the engine."""

    transport: BackendTransport

    def inventory(self) -> PluginInventory:
        payload = self.transport.request("GET", "/packs")
        return self._to_inventory(payload)

    def reload(self) -> PluginInventory:
        payload = self.transport.request("POST", "/packs/reload")
        return self._to_inventory(payload)

    def detail(self, slug: str) -> PluginView:
        payload = self.transport.request("GET", f"/packs/{slug}")
        return PluginView.from_payload(payload if isinstance(payload, Mapping) else {})

    def enable(self, slug: str) -> PluginView:
        return self._toggle(slug, "enable")

    def disable(self, slug: str) -> PluginView:
        return self._toggle(slug, "disable")

    def _toggle(self, slug: str, action: str) -> PluginView:
        payload = self.transport.request("POST", f"/packs/{slug}/{action}")
        return PluginView.from_payload(payload if isinstance(payload, Mapping) else {})

    def validate(self, slug: str) -> ValidationReport:
        payload = self.transport.request("POST", f"/packs/{slug}/validate")
        body: Mapping[str, Any] = payload if isinstance(payload, Mapping) else {}
        raw_checks = body.get("checks")
        checks = tuple(
            ValidationCheck(
                name=as_str(check, "name"),
                passed=as_bool(check, "passed"),
                detail=as_str(check, "detail"),
            )
            for check in (raw_checks if isinstance(raw_checks, Sequence) else [])
            if isinstance(check, Mapping)
        )
        return ValidationReport(
            slug=as_str(body, "slug", slug),
            valid=as_bool(body, "valid", not any(not c.passed for c in checks)),
            checks=checks,
        )

    @staticmethod
    def _to_inventory(payload: object) -> PluginInventory:
        rows = payload.get("packs", []) if isinstance(payload, Mapping) else []
        plugins = [PluginView.from_payload(row) for row in rows if isinstance(row, Mapping)]
        return PluginInventory(
            active=tuple(p for p in plugins if p.healthy),
            rejected=tuple(p for p in plugins if not p.healthy),
        )
