"""SDK exception hierarchy.

Every exception here descends from :class:`~ragstrike.core.errors.RAGStrikeError`, so nothing
raised through the SDK escapes the CLI's existing exit-code mapping (``cli/main.py``) or the
scheduler's per-plugin isolation guard (``scheduler/scan_scheduler.py``) -- both already catch
``RAGStrikeError`` and its subclasses. The SDK does not introduce a second error taxonomy; it
extends the one Phase 3/4 already established, with names a plugin author reaches for naturally.

Three exceptions here are genuinely new concepts the engine had no name for yet
(:class:`PayloadError`, :class:`ValidationError`, :class:`PluginConfigurationError`). The other two
(:class:`TargetConnectionError`, :class:`PluginTimeoutError`) are SDK-facing synonyms for existing
``core.errors`` types, so plugin code can catch a name that reads naturally without knowing the
engine's internal taxonomy -- while ``except TargetUnreachableError`` in engine code still catches
them, because they *are* that type.

**Why not a class literally named ``TimeoutError``.** The Phase 5 brief names one exception
``TimeoutError``. Python's builtin already owns that name, and shadowing it inside this module
would make ``except TimeoutError`` ambiguous to a reader who does not know which one is in scope --
exactly the confusion the ``requests`` library sidesteps by calling its own version ``Timeout``
rather than ``TimeoutError``. :class:`PluginTimeoutError` follows the same precedent.
"""

from __future__ import annotations

from ragstrike.core.errors import (
    ConfigurationError,
    PluginError,
    RAGStrikeError,
    TargetTimeoutError,
    TargetUnreachableError,
)


class SdkError(RAGStrikeError):
    """Base for every exception the SDK raises that has no closer existing home.

    Plugin authors who want to catch "anything the SDK itself raised, as opposed to something my
    own attack logic raised" can catch this. It is deliberately narrow -- most SDK failures map
    onto a more specific type below.
    """

    code = "sdk_error"


class PayloadError(PluginError):
    """A payload file could not be parsed, or a payload entry is malformed.

    Raised by :mod:`ragstrike.sdk.payload_loader` in strict mode. In lenient mode (the SDK
    loader's default) malformed *entries* are skipped and logged instead of raising; this
    exception is reserved for failures lenient mode cannot recover from, such as a file that is
    not valid YAML/JSON/text at all.
    """

    code = "payload_error"


class ValidationError(SdkError):
    """A reusable validator in :mod:`ragstrike.sdk.validators` failed a hard check.

    Distinct from :class:`~ragstrike.plugins.base.reports.ValidationReport`, which is the
    structured, non-raising report the framework uses at plugin-load time. This exception is for
    the SDK's assert-style validators, used inside ``execute()``/``analyze()`` when a plugin wants
    to fail loudly on a malformed response rather than silently treat it as evidence of nothing.
    """

    code = "validation_error"


class TargetConnectionError(TargetUnreachableError):
    """SDK-facing synonym for :class:`~ragstrike.core.errors.TargetUnreachableError`.

    The adapter layer already raises ``TargetUnreachableError`` for connection failures; this
    class exists so plugin code reads naturally (``except TargetConnectionError``) without a
    plugin author needing to know the engine's internal error module. It is never raised by the
    engine itself -- only useful if a plugin's own helper code wants to raise the same category
    of error under a name that matches what it just tried to do.
    """

    code = "target_connection_error"


class PluginConfigurationError(ConfigurationError):
    """A plugin's own configuration (``context.config``) is invalid.

    Distinct from the framework's :class:`~ragstrike.core.errors.ConfigurationError`, which covers
    ``config.yaml``/``targets.yaml``/``plugins.yaml``. This one is for a plugin's ``validate()`` or
    ``setup()`` to raise when its *own* options block is malformed in a way its declared
    validation checks did not already catch.
    """

    code = "plugin_configuration_error"


class PluginTimeoutError(TargetTimeoutError):
    """SDK-facing synonym for :class:`~ragstrike.core.errors.TargetTimeoutError`.

    See the module docstring for why this is not named ``TimeoutError``.
    """

    code = "plugin_timeout_error"


__all__ = [
    "PayloadError",
    "PluginConfigurationError",
    "PluginTimeoutError",
    "SdkError",
    "TargetConnectionError",
    "ValidationError",
]
