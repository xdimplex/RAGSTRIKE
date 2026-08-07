"""``ScanContext`` -- the richer, scan-time companion to ``PluginContext``.

Phase 4's :class:`~ragstrike.plugins.base.context.PluginContext` is built once, at **plugin load
time**, by the registry, from the plugin's manifest and ``configs/plugins.yaml``. It is what makes
dependency injection real: a plugin never instantiates its own logger, never reads YAML itself,
never picks its own timeout.

``ScanContext`` is a different moment in time. The Phase 5 brief asks for a context object that
also carries the **target**, the **scan id**, and (optionally) a **database** handle -- none of
which exist yet when a plugin is *constructed*. They exist only once a scan is *running*, and
Phase 3/4 already fixed the shape of that moment:
:meth:`~ragstrike.plugins.base.attack.BaseAttack.execute` receives the target directly as a
parameter, and the scheduler mints the scan id before calling any plugin method.

Extending :meth:`BaseAttack.execute`'s signature to also take a ``ScanContext`` would be exactly
the kind of architecture change this phase is not allowed to make. So ``ScanContext`` is built
**by the plugin, from information the plugin already has**, entirely inside the SDK -- zero
changes to ``plugins/base/attack.py`` or the scheduler:

    async def execute(self, target, payloads):
        scan_ctx = ScanContext.from_plugin_context(
            self.context, target=target, scan_id=self.context.config.get("_scan_id", "")
        )
        ...

This is dependency injection in the sense the brief asks for -- a plugin never constructs its own
logger, config, or target descriptor from scratch -- just assembled at the point in the code where
all the pieces are already in scope, rather than threaded through a new constructor parameter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import TYPE_CHECKING, Any

from ragstrike.plugins.base.context import PluginContext
from ragstrike.sdk.constants import FRAMEWORK_VERSION

if TYPE_CHECKING:  # pragma: no cover
    from ragstrike.core.contracts.target_adapter import TargetAdapter


@dataclass(frozen=True, slots=True)
class ScanContext:
    """Everything the Phase 5 brief asks a plugin to have access to, in one object.

    Attributes:
        configuration: The plugin's own runtime config -- same dict as
            ``PluginContext.config``, i.e. manifest options merged with ``plugins.yaml``
            overrides. Not the *engine's* global settings; a plugin never needs those.
        logger: Bound with the plugin's slug, same instance as ``PluginContext.logger``.
        target: The adapter the current scan is running against. ``None`` outside of
            ``execute()``, where the engine has not handed one to the plugin yet.
        database: Reserved. Always ``None`` in the current engine wiring -- see the note below.
        current_plugin: The plugin's own slug, so shared helper functions that accept a
            ``ScanContext`` can log or tag evidence with "which plugin called me" without a
            second parameter.
        scan_id: The current scan's id, when the caller knows it. Empty string otherwise.
        framework_version: ``ragstrike.__version__`` at the time this context was built.

    **Why ``database`` is always ``None`` today.** Plugins never instantiate the database
    directly (Phase 4's dependency-injection rule) and no version of the engine currently injects
    a *read* handle into plugin code either -- ``core/orchestrator`` and the repositories are
    engine-internal. This field exists so that a future read-only, repository-backed accessor
    (e.g. "has this target failed this check before?") has a place to arrive without another
    signature change; until that lands, code that checks ``if ctx.database is not None`` will
    always take the "unavailable" branch, and that is correct, not a bug.
    """

    configuration: dict[str, Any] = field(default_factory=dict)
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("ragstrike.plugin"))
    target: TargetAdapter | None = None
    database: Any | None = None
    current_plugin: str = ""
    scan_id: str = ""
    framework_version: str = FRAMEWORK_VERSION

    @classmethod
    def from_plugin_context(
        cls,
        plugin_context: PluginContext,
        *,
        target: TargetAdapter | None = None,
        scan_id: str = "",
    ) -> ScanContext:
        """Derive a :class:`ScanContext` from the :class:`PluginContext` every plugin already has.

        Call this from inside ``execute()``, where ``target`` is already a parameter:

            scan_ctx = ScanContext.from_plugin_context(self.context, target=target)

        Non-destructive: ``plugin_context`` is untouched, and nothing about Phase 4's context
        construction changes. This only reads from it.
        """
        return cls(
            configuration=dict(plugin_context.config),
            logger=plugin_context.logger,
            target=target,
            database=None,
            current_plugin=plugin_context.plugin_id,
            scan_id=scan_id,
            framework_version=FRAMEWORK_VERSION,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializable snapshot. ``target`` and ``database`` are summarized, not dumped --
        neither is meaningfully JSON-serializable, and evidence should describe them, not embed
        them."""
        return {
            "configuration": self.configuration,
            "target": repr(self.target) if self.target is not None else None,
            "database_available": self.database is not None,
            "current_plugin": self.current_plugin,
            "scan_id": self.scan_id,
            "framework_version": self.framework_version,
        }
