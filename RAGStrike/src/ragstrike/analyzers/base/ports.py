"""Ports the Analyzer Engine defines and something else implements.

**Why a port rather than an import.** ``ragstrike.analyzers`` sits *below* ``ragstrike.database`` in
the layer contract, so the engine cannot import a repository -- and that is the right direction.
Analysis is a pure transformation from observations to findings; making it depend on SQLite would
mean the whole engine could only be tested with a database attached.

So the engine declares what it needs and the database layer implements it. ``database`` may import
``analyzers`` because it is higher; the reverse is a contract violation ``lint-imports`` catches.

Both protocols are ``@runtime_checkable`` so a test can assert a class satisfies one without
inheriting from it.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ragstrike.analyzers.base.finding import Finding


@runtime_checkable
class FindingRepository(Protocol):
    """Persistence for findings. Implemented in ``database/repositories/``."""

    async def add_findings(self, findings: list[Finding]) -> None:
        """Store *findings*. Called once per analysis run rather than per finding, so a scan's
        results land in one transaction."""
        ...

    async def findings_for(self, scan_id: str) -> list[Finding]:
        """Every finding recorded for *scan_id*, oldest first."""
        ...


@runtime_checkable
class Analyzer(Protocol):
    """What the registry accepts.

    Deliberately narrower than :class:`~ragstrike.analyzers.base.analyzer.BaseAnalyzer`: a third
    party can satisfy this with any class exposing a name and an ``analyze`` method, without
    inheriting from anything of ours.
    """

    name: str

    def analyze(self, observation: object) -> object:
        """Turn one observation into one finding."""
        ...


__all__ = ["Analyzer", "FindingRepository"]
