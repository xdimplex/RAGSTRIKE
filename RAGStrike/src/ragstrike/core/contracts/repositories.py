"""Persistence ports.

WHY THESE EXIST RATHER THAN IMPORTING THE REPOSITORIES DIRECTLY
    ``ScanEngine`` lives in the application layer; the concrete repositories live in the adapters
    layer. The dependency rule points inward, so the engine cannot name ``ScanRepository`` --
    ``lint-imports`` fails the build if it tries, and rightly.

    Before these Protocols existed the parameters were simply left **unannotated**, which passed the
    layer contract by saying nothing at all. That is the worst of both worlds: the composition
    root's most important wiring had no contract, and ``mypy`` reported it as an untyped def for
    five phases.

    A Protocol resolves it properly. The engine depends on the *shape* it uses, the concrete
    repositories satisfy it structurally without importing anything, and no inward-pointing arrow is
    created in either direction.

WHY THE METHOD SETS ARE NARROW
    Each Protocol declares only what ``ScanEngine`` actually calls. A port that mirrors every method
    of its implementation is not a port, it is a second copy of the class -- and it grows every time
    the implementation does, which is the coupling the port was meant to prevent.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol

from ragstrike.models.entities.scan import PluginResult, ScanSession
from ragstrike.models.entities.target import Target


class ScanRepositoryPort(Protocol):
    """What the engine needs from scan storage."""

    async def create(self, scan: ScanSession, *, config_snapshot: dict[str, Any]) -> None:
        """Persist a new session together with the configuration that produced it."""
        ...

    async def update(self, scan: ScanSession) -> None:
        """Persist a state transition."""
        ...

    async def add_results(self, results: Sequence[PluginResult]) -> None:
        """Persist the per-plugin outcomes of a completed scan."""
        ...


class FindingRepositoryPort(Protocol):
    """What the engine needs to persist analysis output.

    Optional: an engine constructed without one still scans, it simply produces no findings. That
    is how the CLI behaved for thirteen phases, and keeping the port optional means a caller that
    only wants raw plugin results does not have to build an analyzer to get them.
    """

    async def add_findings(self, findings: list[Any]) -> None:
        """Persist the findings produced by one scan."""
        ...


class TargetRepositoryPort(Protocol):
    """What the engine needs from target storage."""

    async def upsert(self, target: Target) -> Target:
        """Record *target*, returning it carrying its stable persisted id.

        The returned id is the one scan history joins on -- ``targets.yaml`` mints a fresh id on
        every load, so the engine must use what comes back rather than what it sent.
        """
        ...


__all__ = ["FindingRepositoryPort", "ScanRepositoryPort", "TargetRepositoryPort"]
