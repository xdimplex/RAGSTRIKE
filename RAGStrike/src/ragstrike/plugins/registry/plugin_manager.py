"""``PluginManager`` -- the operator-facing surface.

Distinct from :class:`PluginRegistry`, which is the engine-facing one. The registry decides which
plugins run *this scan*; the manager mutates the state that governs *future* scans -- persisting
enable/disable to ``plugins.yaml``, forcing rediscovery, running validation on demand.

The split matters because they have different failure modes. A registry error aborts a scan; a
manager error should never do that, because a broken ``plugins enable`` in the CLI has to be
survivable without corrupting the running engine. Keeping the write path in this class means the
engine never mutates plugin state.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from ragstrike.plugins.base.reports import ValidationReport
from ragstrike.plugins.events import PluginEvent, PluginEventType
from ragstrike.plugins.registry.plugin_registry import (
    LoadedPlugin,
    PluginHealth,
    PluginRegistry,
    RejectedPlugin,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PluginSummary:
    """One row of ``ragstrike plugins list``. Small on purpose."""

    slug: str
    name: str
    version: str
    category: str
    severity: str
    enabled: bool
    active: bool
    source: str


@dataclass(frozen=True, slots=True)
class PluginInfo:
    """Everything ``ragstrike plugins info`` shows.

    Kept separate from :class:`PluginSummary` because ``list`` should stay fast and terse; ``info``
    reads a plugin's whole metadata and does not want to inflate the list view.
    """

    summary: PluginSummary
    description: str
    author: str
    owasp_mapping: tuple[str, ...]
    references: tuple[str, ...]
    tags: tuple[str, ...]
    required_target_type: str
    min_framework_version: str
    requires_api: str
    requires_capabilities: tuple[str, ...]
    license: str
    permissions: dict[str, bool]
    manifest_path: str
    options: dict[str, Any]


class PluginManager:
    """Operator-facing plugin operations.

    Wraps a :class:`PluginRegistry` and (optionally) writes back into the ``plugins.yaml`` the
    registry loaded. The write path exists to support the CLI's ``enable``/``disable`` subcommands;
    no other caller mutates plugin state.
    """

    def __init__(self, registry: PluginRegistry) -> None:
        self.registry = registry

    # -- reads --------------------------------------------------------------------------------

    def summaries(self) -> list[PluginSummary]:
        """Every plugin the framework sees, active or refused, in slug order.

        NOT named ``list``. A method called ``list`` on this class shadows the builtin inside every
        annotation in the class body, so ``-> list[PluginSummary]`` silently resolved to
        ``PluginManager.list[...]``. Nothing failed at runtime -- ``from __future__ import
        annotations`` keeps annotations as strings -- but mypy could not type this method or
        :meth:`validate`, and the CLI's ``for slug, report in reports`` was reported as iterating a
        non-iterable. The CLI subcommand is still ``plugins list``; only the Python name changed.
        """
        health = self.registry.discover()
        summaries: list[PluginSummary] = [
            self._summarize_active(plugin) for plugin in health.active
        ]
        summaries += [self._summarize_rejected(rejected) for rejected in health.rejected]
        return sorted(summaries, key=lambda s: s.slug)

    def info(self, slug: str) -> PluginInfo | None:
        """Detailed metadata for one plugin. ``None`` if the framework has never seen it."""
        health = self.registry.discover()
        for plugin in health.active:
            if plugin.slug == slug:
                return self._info_for_active(plugin)
        return None

    def health(self) -> PluginHealth:
        return self.registry.discover()

    # -- writes -------------------------------------------------------------------------------

    def enable(self, slug: str) -> bool:
        """Enable *slug* by writing to ``plugins.yaml``.

        Returns ``True`` if the change was written. Returns ``False`` when there is no
        ``plugins.yaml`` to write to -- which happens when the operator never configured one, and
        which is not an error: the plugin was already enabled by default.
        """
        return self._set_enabled(slug, True, PluginEventType.ENABLED)

    def disable(self, slug: str) -> bool:
        """Disable *slug* by writing to ``plugins.yaml``."""
        return self._set_enabled(slug, False, PluginEventType.DISABLED)

    def reload(self) -> PluginHealth:
        """Force re-discovery.

        Modules are not re-imported: Python's import system caches them, and blowing that cache
        away for third-party code is a good way to end up with two versions of a class in memory.
        The registry's ``discover(force=True)`` refreshes state that CAN be refreshed -- runtime
        config, capability filtering, health -- and everything else keeps its cached instance.
        """
        return self.registry.discover(force=True)

    def validate(self, slug: str | None = None) -> list[tuple[str, ValidationReport]]:
        """Framework + plugin validation, on demand."""
        return self.registry.validate(slug)

    # -- internals ----------------------------------------------------------------------------

    def _set_enabled(self, slug: str, enabled: bool, event: PluginEventType) -> bool:
        # Ensure the config store is loaded. discover() reads plugins.yaml; without calling it
        # here, an operator who runs `ragstrike plugins disable X` before any scan would see the
        # write silently no-op.
        self.registry.discover()
        store = self.registry.plugin_config
        if store is None or store.path is None:  # pragma: no cover - defensive
            log.warning("no plugin config path configured; cannot persist", extra={"slug": slug})
            return False

        store.set_enabled(slug, enabled)
        store.save()
        self.registry.events.publish(PluginEvent(type=event, plugin_slug=slug))
        log.info("plugin state changed", extra={"slug": slug, "enabled": enabled})
        return True

    def _summarize_active(self, plugin: LoadedPlugin) -> PluginSummary:
        meta = plugin.metadata()
        return PluginSummary(
            slug=plugin.slug,
            name=meta.name,
            version=plugin.version,
            category=meta.category,
            severity=meta.severity.value,
            enabled=True,
            active=True,
            source=str(plugin.manifest.source),
        )

    def _summarize_rejected(self, rejected: RejectedPlugin) -> PluginSummary:
        return PluginSummary(
            slug=rejected.slug,
            name=rejected.slug,
            version="-",
            category=rejected.reason,
            severity="-",
            enabled=False,
            active=False,
            source=rejected.source,
        )

    def _info_for_active(self, plugin: LoadedPlugin) -> PluginInfo:
        meta = plugin.metadata()
        manifest = plugin.manifest
        return PluginInfo(
            summary=self._summarize_active(plugin),
            description=meta.description,
            author=meta.author,
            owasp_mapping=meta.owasp_llm,
            references=meta.references,
            tags=meta.tags,
            required_target_type=meta.required_target_type,
            min_framework_version=meta.min_framework_version,
            requires_api=meta.requires_api,
            requires_capabilities=tuple(c.value for c in meta.requires_capabilities),
            license=meta.license,
            permissions={
                "network_egress": manifest.permissions.network_egress,
                "filesystem_write": manifest.permissions.filesystem_write,
            },
            manifest_path=str(manifest.manifest_path),
            options=dict(manifest.options),
        )
