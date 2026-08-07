"""Framework-wide constants for plugin authors.

Values here are the SDK's committed defaults -- the numbers a plugin gets if it does not think
about timeouts, retries, or headers at all. They intentionally mirror the engine's own defaults
(``configs/config.yaml``, ``core/config/models.py``) so a plugin built against these constants
behaves the same as the framework's out-of-the-box configuration, without importing the engine's
Pydantic settings machinery just to read one number.

**These are defaults, not enforcement.** An operator's ``configs/plugins.yaml`` (``timeout``,
``severity_override``) always wins over anything here -- see
:class:`~ragstrike.plugins.base.context.PluginContext`.
"""

from __future__ import annotations

from typing import Final

from ragstrike import PLUGIN_API_VERSION, __version__

#: Re-exported so plugin code can do ``from ragstrike.sdk.constants import FRAMEWORK_VERSION``
#: instead of reaching into the ``ragstrike`` package root directly.
FRAMEWORK_VERSION: Final[str] = __version__

#: Re-exported for the same reason. This is the value plugin manifests compare their
#: ``compatibility.ragstrike_api`` range against (ADR-015) -- not ``FRAMEWORK_VERSION``.
SDK_PLUGIN_API_VERSION: Final[str] = PLUGIN_API_VERSION

#: Seconds. Matches ``EngineSettings.probe_timeout_s`` in ``core/config/models.py``.
DEFAULT_TIMEOUT_S: Final[int] = 60

#: Attempts for the SDK's retry helper (:func:`ragstrike.sdk.helpers.retry.retry_async`).
#: Transport-level failures only -- a semantically valid response, even a refusal, is never
#: retried (see ``core/executor`` design notes in the SDD).
DEFAULT_RETRY_COUNT: Final[int] = 3

#: Seconds. Base delay before the first retry; the retry helper backs off exponentially from here.
DEFAULT_RETRY_BACKOFF_S: Final[float] = 1.0

#: Ceiling on the exponential backoff, so a flaky target cannot stall a scan indefinitely.
DEFAULT_RETRY_MAX_BACKOFF_S: Final[float] = 30.0

#: Sent by :class:`~ragstrike.sdk.request_builder.TargetRequestBuilder` unless overridden.
#: Mirrors what ``target_adapters/fastapi/adapter.py`` already sets on its own ``httpx.AsyncClient``.
DEFAULT_HEADERS: Final[dict[str, str]] = {
    "User-Agent": f"RAGStrike-SDK/{FRAMEWORK_VERSION}",
}

#: Payload tiers a plugin's payload set may declare (SDD Annex B). The SDK does not enforce these
#: -- ``Payload.tier`` is a free-form string -- but sticking to this set keeps a plugin's payloads
#: filterable by future profile-based scan selection (``configs/profiles/*.yaml``).
PAYLOAD_TIER_QUICK: Final[str] = "quick"
PAYLOAD_TIER_STANDARD: Final[str] = "standard"
PAYLOAD_TIER_DEEP: Final[str] = "deep"
PAYLOAD_TIERS: Final[tuple[str, ...]] = (
    PAYLOAD_TIER_QUICK,
    PAYLOAD_TIER_STANDARD,
    PAYLOAD_TIER_DEEP,
)


class ConfigKeys:
    """Namespaced key names used in ``configs/plugins.yaml`` and plugin manifests.

    Not an enum: these are used as dict keys against YAML-sourced ``dict[str, Any]`` values (
    :attr:`~ragstrike.plugins.base.context.PluginContext.config`), so plain string constants avoid
    an unnecessary ``.value`` at every call site. Grouped in a class purely for
    ``ConfigKeys.ENABLED``-style discoverability.
    """

    ENABLED: Final[str] = "enabled"
    TIMEOUT: Final[str] = "timeout"
    SEVERITY_OVERRIDE: Final[str] = "severity_override"
    CONFIG: Final[str] = "config"


__all__ = [
    "DEFAULT_HEADERS",
    "DEFAULT_RETRY_BACKOFF_S",
    "DEFAULT_RETRY_COUNT",
    "DEFAULT_RETRY_MAX_BACKOFF_S",
    "DEFAULT_TIMEOUT_S",
    "FRAMEWORK_VERSION",
    "PAYLOAD_TIERS",
    "PAYLOAD_TIER_DEEP",
    "PAYLOAD_TIER_QUICK",
    "PAYLOAD_TIER_STANDARD",
    "SDK_PLUGIN_API_VERSION",
    "ConfigKeys",
]
