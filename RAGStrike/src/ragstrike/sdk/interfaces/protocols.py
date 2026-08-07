"""Protocols for the SDK's own building blocks.

These formalize what a request builder, a response parser, and a validator *are*, independent of
the SDK's own implementations (:mod:`ragstrike.sdk.request_builder`,
:mod:`ragstrike.sdk.response_parser`, ...). Two reasons to have them:

1. **Testing.** A plugin's unit tests can substitute a fake response parser that satisfies
   :class:`ResponseParserProtocol` without importing httpx or constructing a real
   ``TargetResponse``.
2. **Alternate implementations.** If a future plugin pack wants a parser tuned for a
   non-JSON target (plain-text completions, say), it can implement this protocol directly rather
   than subclassing the SDK's concrete class.

None of this is enforced by the engine -- Phase 3/4's actual contract for a plugin remains
:class:`~ragstrike.plugins.base.attack.BaseAttack`. These protocols describe the SDK layer beneath
it, not a second engine contract.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ragstrike.core.contracts.target_adapter import TargetRequest


@runtime_checkable
class RequestBuilderProtocol(Protocol):
    """Anything that can produce a :class:`TargetRequest`."""

    def build(self) -> TargetRequest:
        """Return the assembled request. Must not send anything -- building is not sending."""
        ...


@runtime_checkable
class ResponseParserProtocol(Protocol):
    """Anything that can extract structured facts out of a :class:`TargetResponse`."""

    def text(self) -> str: ...
    def json(self) -> Any | None: ...
    def chunks(self) -> list[dict[str, Any]]: ...
    def sources(self) -> list[str]: ...
    def error(self) -> str: ...


@runtime_checkable
class ValidatorProtocol(Protocol):
    """A single reusable check: given a value, is it acceptable?

    Every function in :mod:`ragstrike.sdk.validators` satisfies this shape, which is what lets
    :func:`ragstrike.sdk.validators.validators.run_all` accept a list of them interchangeably.
    """

    def __call__(self, value: Any) -> bool: ...


@runtime_checkable
class ResultBuilderProtocol(Protocol):
    """Anything that can be told about a payload's outcome and asked for a finished result."""

    def build(self) -> Any:
        """Return the finished result object. Shape is the implementation's choice; the SDK's
        own builder returns :class:`~ragstrike.sdk.base.result.AttackResult`."""
        ...


__all__ = [
    "RequestBuilderProtocol",
    "ResponseParserProtocol",
    "ResultBuilderProtocol",
    "ValidatorProtocol",
]
