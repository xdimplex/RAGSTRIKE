"""The Target Adapter port.

**The only view the attack engine has of a system under test.** This is what delivers goal G3: the
engine never learns whether it is attacking Ollama, OpenAI, LangChain, or bespoke Python. Provider
knowledge lives in ``target_adapters/`` and nowhere else.

Layer 1. Declarations only -- no implementation, no I/O, no provider-specific concepts.

Phase 3 implements exactly one adapter (``FastAPIAdapter``). The port is defined in full now so that
adding the second one is a new file rather than a change to this one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from ragstrike.models.values.enums import Capability


@dataclass(frozen=True, slots=True)
class TargetRequest:
    """One thing the engine wants to send."""

    prompt: str
    session_id: str | None = None
    #: Opaque passthrough for adapters that need it. The engine never inspects this.
    metadata: dict[str, Any] = field(default_factory=dict)
    timeout_s: int | None = None
    correlation_id: str = ""


@dataclass(frozen=True, slots=True)
class TargetResponse:
    """What came back.

    ``raw`` is retained verbatim. The engine does not interpret it, but a detector or a human
    reviewing a finding may need the part the adapter chose not to map.
    """

    text: str
    latency_ms: int = 0
    retrieved_chunks: list[dict[str, Any]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    session_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


@dataclass(frozen=True, slots=True)
class TargetDescriptor:
    """What an adapter says about itself."""

    adapter: str
    version: str
    url: str
    capabilities: tuple[Capability, ...] = ()

    def supports(self, capability: Capability) -> bool:
        return capability in self.capabilities


@dataclass(frozen=True, slots=True)
class HealthResult:
    """Cheap liveness probe. Never raises -- a health check reports, it does not propagate."""

    reachable: bool
    latency_ms: int = 0
    detail: str = ""


@runtime_checkable
class TargetAdapter(Protocol):
    """Every system under test looks like this to the engine.

    Four operations are mandatory. Anything conditional -- document ingestion, source listing,
    session reset -- is declared through :class:`~ragstrike.models.values.enums.Capability` and
    negotiated before an attack that needs it is ever scheduled.

    Implementations must declare capabilities **honestly**. The scheduler trusts the declaration,
    and an overstated one corrupts the coverage figure every result is qualified by -- which is
    worse than declaring fewer capabilities than you have.
    """

    def describe(self) -> TargetDescriptor:
        """Identity, version, and declared capabilities."""
        ...

    async def health_check(self) -> HealthResult:
        """Is the target reachable? Must not raise."""
        ...

    async def chat(self, request: TargetRequest) -> TargetResponse:
        """Send a prompt and return the response."""
        ...

    async def close(self) -> None:
        """Release connections."""
        ...
