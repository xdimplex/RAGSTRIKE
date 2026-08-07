"""Error taxonomy.

Everything the framework raises deliberately descends from :class:`RAGStrikeError`. The CLI maps
each family onto a distinct exit code so a pipeline can tell *"the target is insecure"* from
*"the scanner is misconfigured"* -- those demand opposite responses, and a single non-zero exit
conflates them.
"""

from __future__ import annotations


class RAGStrikeError(Exception):
    """Base for every deliberate failure."""

    code = "internal_error"

    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        #: What the operator should do about it. Printed by the CLI beneath the error.
        self.hint = hint


# -- configuration -------------------------------------------------------------------------------


class ConfigurationError(RAGStrikeError):
    """Malformed or missing configuration. Raised at startup, before anything runs."""

    code = "configuration_error"


class TargetNotFoundError(ConfigurationError):
    """No target with that name in ``targets.yaml``."""

    code = "target_not_found"


class AuthorizationError(RAGStrikeError):
    """The target has no authorization record.

    Not a configuration error, deliberately: a missing authorization is a *refusal to proceed*, not
    a typo, and it gets its own exit code so a pipeline can surface it as such (ADR-017).
    """

    code = "authorization_missing"


# -- plugins -------------------------------------------------------------------------------------


class PluginError(RAGStrikeError):
    code = "plugin_error"


class PluginLoadError(PluginError):
    """A plugin directory exists but could not be turned into a usable plugin."""

    code = "plugin_load_error"


class IncompatiblePluginError(PluginError):
    """The plugin declares an API range this engine does not satisfy."""

    code = "plugin_incompatible"


class PluginConflictError(PluginError):
    """Two plugins claim the same slug."""

    code = "plugin_conflict"


# -- targets -------------------------------------------------------------------------------------


class TargetError(RAGStrikeError):
    code = "target_error"


class TargetUnreachableError(TargetError):
    code = "target_unreachable"


class TargetTimeoutError(TargetError):
    code = "target_timeout"


class TargetProtocolError(TargetError):
    """The target responded, but not in a shape this adapter understands."""

    code = "target_protocol_error"


class UnknownAdapterError(ConfigurationError):
    """``targets.yaml`` names an adapter that is not registered."""

    code = "unknown_adapter"


# -- persistence ---------------------------------------------------------------------------------


class PersistenceError(RAGStrikeError):
    code = "persistence_error"
