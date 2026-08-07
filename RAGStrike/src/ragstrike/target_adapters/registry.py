"""Adapter registry.

Maps the ``adapter`` field in ``targets.yaml`` to a concrete class. Registration is explicit rather
than magic: adapters are a small, closed, first-party set, and an explicit table is easier to read
than an import scan.

This is the only module in the codebase that knows every adapter by name -- deliberately, so nothing
else does. The engine reaches targets through
:class:`~ragstrike.core.contracts.target_adapter.TargetAdapter` and never learns which one it got.

Phase 3 registers ``fastapi``. The others are named in the error message so that asking for one
tells you it is planned rather than mistyped.
"""

from __future__ import annotations

from collections.abc import Sequence
import inspect
from typing import Any, cast

from ragstrike.core.config.models import RetrySettings
from ragstrike.core.errors import UnknownAdapterError
from ragstrike.models.entities.target import Target
from ragstrike.target_adapters.base.base_target import BaseTarget
from ragstrike.target_adapters.fastapi.adapter import FastAPIAdapter

ADAPTERS: dict[str, type[BaseTarget]] = {
    FastAPIAdapter.adapter_name: FastAPIAdapter,
}

#: Declared in the SDD, not yet implemented. Listed so an operator asking for one gets "planned"
#: rather than "unknown adapter", which are very different messages.
PLANNED: dict[str, str] = {
    "openai": "Phase 11",
    "ollama": "Phase 11",
    "langchain": "Phase 12",
    "llamaindex": "Phase 12",
    "local": "Phase 3+ (Python in-process)",
}


def build_adapter(
    target: Target,
    *,
    allow_remote: bool = False,
    allowed_hosts: Sequence[str] | None = None,
    retry: RetrySettings | None = None,
) -> BaseTarget:
    """Construct the adapter named by *target*, refusing out-of-scope hosts.

    **The scope check runs here, at the single construction chokepoint, and the defaults are the
    restrictive ones.** Phase 6 moved it here from the call sites. It previously lived only in
    ``cli/main.py`` beside the scan command, which meant the guarantee held exactly as long as
    every future call site remembered to repeat it -- and ``ragstrike targets --verify`` already
    did not, so it probed every configured host, loopback or not, before anyone noticed.

    Defaulting to ``allow_remote=False`` with an empty allowlist means a caller who forgets to
    thread the operator's configuration through gets the *safe* behaviour rather than the
    permissive one. Forgetting now makes the tool too strict, which someone reports; the previous
    arrangement made it too permissive, which nobody notices until it has already reached
    something it should not have. Loopback needs no allowlist entry -- ``assert_allowed`` treats
    it as always in scope -- so the shipped default of "no allowlist at all" is precisely the
    localhost-only policy, not an approximation of it.

    Args:
        target: The target to build an adapter for.
        allow_remote: ``safety.allow_remote_targets``. Left false, non-loopback is refused.
        allowed_hosts: ``safety.allowed_hosts``. Extra hosts permitted *in addition to* loopback,
            and only consulted when the operator has also set ``allow_remote``.
        retry: ``engine.retry``. Adapters that do their own transport retry take it here rather
            than reading configuration themselves -- an adapter that loaded its own settings would
            be a second, divergent configuration path.

    Raises:
        UnknownAdapterError: The name is neither registered nor planned.
        TargetError: The target's host is out of scope for the current configuration.
    """
    adapter_class = ADAPTERS.get(target.adapter)
    if adapter_class is not None:
        adapter = _construct(adapter_class, target, retry)
        adapter.assert_allowed(
            allow_remote=allow_remote,
            allowed_hosts=list(allowed_hosts or ()),
        )
        return adapter

    if target.adapter in PLANNED:
        raise UnknownAdapterError(
            f"Adapter {target.adapter!r} is planned for {PLANNED[target.adapter]}, "
            f"not implemented yet.",
            hint=f"Use one of: {', '.join(sorted(ADAPTERS))}.",
        )

    raise UnknownAdapterError(
        f"Unknown adapter {target.adapter!r} for target {target.name!r}.",
        hint=f"Available now: {', '.join(sorted(ADAPTERS))}. "
        f"Planned: {', '.join(sorted(PLANNED))}.",
    )


def available() -> list[str]:
    return sorted(ADAPTERS)


def _construct(
    adapter_class: type[BaseTarget], target: Target, retry: RetrySettings | None
) -> BaseTarget:
    """Build an adapter, passing retry settings only to adapters that accept them.

    Adapters are third-party-extensible, so the registry cannot assume every one of them has grown
    a ``retry`` parameter. Introspecting once here keeps a two-argument adapter working rather than
    breaking every external adapter the moment the built-in one gained an option.
    """
    if "retry" in inspect.signature(adapter_class).parameters:
        # Typed loosely on purpose: adapters are third-party-extensible, so the registry knows the
        # base contract and not each subclass's constructor.
        factory: Any = adapter_class
        return cast("BaseTarget", factory(target, retry=retry))
    return adapter_class(target)
