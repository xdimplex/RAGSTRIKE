"""``BaseTarget`` -- shared scaffolding for every adapter.

The port itself is :class:`~ragstrike.core.contracts.target_adapter.TargetAdapter`, at Layer 1.
This is the Layer 3 base class that concrete adapters extend: it centralises capability declaration,
error translation, and the safety check that keeps a fresh install pointed at loopback.

Phase 3 ships one subclass, ``FastAPIAdapter``. The base exists now so the second adapter is a new
file rather than a refactor of the first.
"""

from __future__ import annotations

import abc
import ipaddress
import logging
from urllib.parse import urlparse

from ragstrike.core.contracts.target_adapter import (
    HealthResult,
    TargetDescriptor,
    TargetRequest,
    TargetResponse,
)
from ragstrike.core.errors import TargetError
from ragstrike.models.entities.target import Target
from ragstrike.models.values.enums import Capability

log = logging.getLogger(__name__)


class BaseTarget(abc.ABC):
    """Common behaviour for concrete target adapters."""

    #: Registry key. ``targets.yaml`` names this in its ``adapter`` field.
    adapter_name: str = "base"
    adapter_version: str = "0.1.0"
    #: What this adapter can do. Declare honestly -- an overstated capability corrupts the coverage
    #: figure that every scan result is qualified by.
    default_capabilities: tuple[Capability, ...] = (Capability.CHAT,)

    def __init__(self, target: Target) -> None:
        self.target = target

    # -- contract ---------------------------------------------------------------------------

    def describe(self) -> TargetDescriptor:
        return TargetDescriptor(
            adapter=self.adapter_name,
            version=self.adapter_version,
            url=self.target.url,
            capabilities=self.capabilities(),
        )

    def capabilities(self) -> tuple[Capability, ...]:
        """What the target supports.

        Whatever ``targets.yaml`` declared wins, because an operator who has verified their target
        knows more than an adapter's optimistic default.
        """
        return self.target.capabilities or self.default_capabilities

    @abc.abstractmethod
    async def health_check(self) -> HealthResult:
        """Is the target reachable? Must not raise."""

    @abc.abstractmethod
    async def chat(self, request: TargetRequest) -> TargetResponse:
        """Send a prompt and return the response."""

    @abc.abstractmethod
    async def close(self) -> None:
        """Release connections."""

    # -- safety -----------------------------------------------------------------------------

    def assert_allowed(self, *, allow_remote: bool, allowed_hosts: list[str]) -> None:
        """Refuse to reach a host the operator has not explicitly permitted.

        The shipped configuration allows loopback only. Pointing RAGStrike at anything else takes
        two deliberate steps -- setting ``allow_remote_targets`` *and* adding an allowlist entry --
        because accidentally scanning a third party is an incident, not an inconvenience (ADR-017).

        **Both steps are required, and Phase 6 made that true.** This method previously returned
        early when ``host in allowed_hosts``, which meant an allowlist entry alone was sufficient
        and ``allow_remote_targets: false`` did not actually hold -- an operator who added a host
        for some later purpose, or inherited a shared config, was permitting it immediately while
        the flag still read as off. Both this docstring and ``SafetySettings`` already described
        the two-step rule; the code implemented one step. The rule now matches its documentation,
        which is the direction worth resolving that mismatch in for a safety control.

        Loopback is exempt from both steps and needs no allowlist entry.

        Raises:
            TargetError: The host is not permitted by the current configuration.
        """
        host = urlparse(self.target.url).hostname or ""
        if _is_loopback(host):
            return

        if not allow_remote:
            raise TargetError(
                f"Target {self.target.name!r} points at {host!r}, which is not loopback.",
                hint=(
                    "Set safety.allow_remote_targets: true AND add the host to "
                    "safety.allowed_hosts in configs/config.yaml. Only scan systems you are "
                    "authorized to test."
                ),
            )

        if host not in allowed_hosts:
            raise TargetError(
                f"Host {host!r} is not in safety.allowed_hosts.",
                hint=f"Add {host!r} to safety.allowed_hosts in configs/config.yaml.",
            )

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"<{type(self).__name__} {self.target.name!r} {self.target.url}>"


def _is_loopback(host: str) -> bool:
    if host in {"localhost", ""}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False
