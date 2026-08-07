"""Plugin registry -- discovery policy, compatibility, activation, health.

The loader *finds* candidates; this decides which ones run and what the operator is told about the
rest.

Three rules shape the behaviour:

* **A broken plugin never stops the scan.** It is recorded with a reason and skipped. A security
  tool that refuses to start because one optional extension is malformed simply will not be run.
* **A refusal is never silent.** Every rejected plugin appears in the health report and, later,
  in the report's Coverage section. Silent shadowing would change results invisibly.
* **Duplicate slugs resolve by version**, and the shadowed one is recorded. Two plugins claiming
  the same slug is a conflict, not a coin toss.

Phase 4 adds three things to the Phase 3 registry:

1. Delegates loading to :class:`~ragstrike.plugins.loader.loader.PluginLoader`.
2. Applies runtime configuration from ``plugins.yaml`` (enable/disable/timeout/severity).
3. Publishes plugin lifecycle events (LOADED, DISABLED) through the :class:`EventBus` protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from ragstrike.core.config.models import PluginSettings
from ragstrike.core.errors import PluginLoadError
from ragstrike.plugins.base.attack import AttackMetadata, BaseAttack
from ragstrike.plugins.base.reports import ValidationReport
from ragstrike.plugins.events import EventBus, NoOpBus, PluginEvent, PluginEventType
from ragstrike.plugins.loader.discovery import discover_directories, discover_entry_points
from ragstrike.plugins.loader.loader import PluginLoader
from ragstrike.plugins.loader.manifest import PluginManifest
from ragstrike.plugins.registry.plugin_config import (
    PluginConfigStore,
    PluginRuntimeConfig,
    load_plugin_config,
)
from ragstrike.plugins.registry.validator import validate_manifest

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LoadedPlugin:
    """An activated plugin, ready to run."""

    manifest: PluginManifest
    attack: BaseAttack

    @property
    def slug(self) -> str:
        return self.manifest.slug

    @property
    def version(self) -> str:
        return self.manifest.version

    def metadata(self) -> AttackMetadata:
        return self.attack.metadata()


@dataclass(frozen=True, slots=True)
class RejectedPlugin:
    """A plugin that was found but will not run, and why."""

    slug: str
    source: str
    reason: str
    detail: str = ""


@dataclass(slots=True)
class PluginHealth:
    """What the CLI's ``plugins`` command and the future Coverage section report."""

    active: list[LoadedPlugin] = field(default_factory=list)
    rejected: list[RejectedPlugin] = field(default_factory=list)

    @property
    def inventory(self) -> dict[str, str]:
        """``slug -> version`` for everything that will actually run."""
        return {p.slug: p.version for p in self.active}


class PluginRegistry:
    """Discovers, validates, and activates attack plugins."""

    def __init__(
        self,
        settings: PluginSettings,
        *,
        api_version: str,
        plugin_config_path: Path | None = None,
        loader: PluginLoader | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.settings = settings
        self.api_version = api_version
        self.plugin_config_path = plugin_config_path
        self.loader = loader or PluginLoader()
        self.events: EventBus = event_bus or NoOpBus()
        self._config: PluginConfigStore | None = None
        self._health = PluginHealth()
        self._loaded = False

    # -- public -------------------------------------------------------------------------------

    def discover(self, *, force: bool = False) -> PluginHealth:
        """Find, check, and activate every available plugin.

        Idempotent: the result is cached, because discovery imports third-party code and doing
        that twice in one process is a good way to get two different class objects for one plugin.
        Call with ``force=True`` from the CLI's ``reload`` command.
        """
        if self._loaded and not force:
            return self._health

        self._config = self._load_plugin_config()
        self._health = PluginHealth()
        best: dict[str, tuple[Version | None, PluginManifest]] = {}

        for manifest in self._candidates():
            self._consider(manifest, best)

        for _, manifest in sorted(best.values(), key=lambda item: item[1].slug):
            self._activate(manifest)

        self._loaded = True
        log.info(
            "plugin discovery complete",
            extra={
                "active": len(self._health.active),
                "rejected": len(self._health.rejected),
                "slugs": sorted(self._health.inventory),
            },
        )
        return self._health

    @property
    def health(self) -> PluginHealth:
        return self._health

    @property
    def plugin_config(self) -> PluginConfigStore | None:
        return self._config

    def active(self) -> list[LoadedPlugin]:
        return list(self._health.active)

    def get(self, slug: str) -> LoadedPlugin | None:
        return next((p for p in self._health.active if p.slug == slug), None)

    def validate(self, slug: str | None = None) -> list[tuple[str, ValidationReport]]:
        """Run every validation gate against one plugin or all of them.

        Returns pairs of ``(slug, report)``. A refused-at-load-time plugin appears here with its
        rejection reason; a loaded plugin appears with the combined framework and plugin reports.
        """
        self.discover()
        results: list[tuple[str, ValidationReport]] = []

        for manifest in [m for m in self._all_manifests() if slug is None or m.slug == slug]:
            framework = validate_manifest(manifest, api_version=self.api_version)
            plugin_report = self.loader.validate(manifest)
            merged = framework.merge(plugin_report)

            active = self.get(manifest.slug)
            if active is not None:
                merged = merged.merge(active.attack.validate())
            results.append((manifest.slug, merged))

        return results

    # -- internals ----------------------------------------------------------------------------

    def _load_plugin_config(self) -> PluginConfigStore:
        if self.plugin_config_path is None:
            return PluginConfigStore(path=Path("plugins.yaml"))
        return load_plugin_config(self.plugin_config_path)

    def _candidates(self) -> list[PluginManifest]:
        """Every manifest from every discovery mechanism."""
        found = list(discover_directories(self.settings.local_dirs))

        for name, value in discover_entry_points(self.settings.entry_point_group):
            found.append(
                PluginManifest(
                    slug=name,
                    name=name,
                    version="0.0.0",
                    entry_point=value,
                    source=self.settings.local_dirs[0] if self.settings.local_dirs else Path(),
                    manifest_path=Path(f"<entry-point:{name}>"),
                )
            )
        return found

    def _all_manifests(self) -> list[PluginManifest]:
        """Every manifest ever discovered, active or not.

        Used by :meth:`validate` so an operator can validate a plugin that was refused for
        (say) elevated permissions -- the reason it was refused is itself part of the report.
        """
        return list(self._candidates())

    def _consider(
        self, manifest: PluginManifest, best: dict[str, tuple[Version | None, PluginManifest]]
    ) -> None:
        """Apply policy to one candidate, keeping the winner per slug."""
        if manifest.slug in self.settings.disabled:
            self._reject(manifest, "disabled", "Listed in plugins.disabled.")
            return

        if self._config is not None and self._config.is_disabled(manifest.slug):
            self._reject(manifest, "disabled-in-config", "Disabled in plugins.yaml.")
            self.events.publish(
                PluginEvent(type=PluginEventType.DISABLED, plugin_slug=manifest.slug)
            )
            return

        if not self._api_compatible(manifest):
            self._reject(
                manifest,
                "incompatible",
                f"Requires plugin API {manifest.requires_api}; this engine is {self.api_version}.",
            )
            return

        if manifest.permissions.is_elevated and not self.settings.allow_elevated_permissions:
            self._reject(
                manifest,
                "elevated-permissions",
                f"Requests {manifest.permissions.describe()}. Set "
                f"plugins.allow_elevated_permissions to permit it.",
            )
            return

        version = _parse_version(manifest.version)
        current = best.get(manifest.slug)
        if current is None:
            best[manifest.slug] = (version, manifest)
            return

        # Duplicate slug. Higher version wins; the loser is recorded, never silently dropped.
        current_version, current_manifest = current
        if version is not None and (current_version is None or version > current_version):
            best[manifest.slug] = (version, manifest)
            self._reject(
                current_manifest,
                "shadowed",
                f"Version {current_manifest.version} shadowed by {manifest.version}.",
            )
        else:
            self._reject(
                manifest,
                "shadowed",
                f"Version {manifest.version} shadowed by {current_manifest.version}.",
            )

    def _activate(self, manifest: PluginManifest) -> None:
        runtime = None
        if self._config is not None:
            runtime = self._config.for_plugin(manifest.slug)

        try:
            attack = self.loader.load(manifest, runtime=runtime)
            metadata = attack.metadata()
        except PluginLoadError as exc:
            self._reject(manifest, "load-failed", exc.message)
            return
        except Exception as exc:
            self._reject(manifest, "load-failed", f"{type(exc).__name__}: {exc}")
            return

        if metadata.slug != manifest.slug:
            self._reject(
                manifest,
                "slug-mismatch",
                f"Manifest says {manifest.slug!r}, metadata() says {metadata.slug!r}.",
            )
            return

        # Plugin's own validate() runs at load time and can refuse activation.
        report = attack.validate()
        if not report.valid:
            failures = "; ".join(check.detail or check.rule for check in report.failures)
            self._reject(manifest, "self-validation-failed", failures)
            return

        loaded = LoadedPlugin(manifest=manifest, attack=attack)
        self._health.active.append(loaded)

        self.events.publish(
            PluginEvent(
                type=PluginEventType.LOADED,
                plugin_slug=manifest.slug,
                payload={"version": manifest.version, "source": str(manifest.source)},
            )
        )
        log.info(
            "plugin loaded",
            extra={
                "slug": manifest.slug,
                "plugin_version": manifest.version,
                "category": metadata.category,
                "source": str(manifest.source),
            },
        )

    def _api_compatible(self, manifest: PluginManifest) -> bool:
        try:
            return Version(self.api_version) in SpecifierSet(manifest.requires_api)
        except (InvalidSpecifier, InvalidVersion):
            return False

    def _reject(self, manifest: PluginManifest, reason: str, detail: str) -> None:
        self._health.rejected.append(
            RejectedPlugin(
                slug=manifest.slug,
                source=str(manifest.source),
                reason=reason,
                detail=detail,
            )
        )
        log.warning(
            "plugin rejected",
            extra={"slug": manifest.slug, "reason": reason, "detail": detail},
        )


def _parse_version(raw: str) -> Version | None:
    try:
        return Version(raw)
    except InvalidVersion:
        return None


__all__ = [
    "LoadedPlugin",
    "PluginHealth",
    "PluginRegistry",
    "PluginRuntimeConfig",
    "RejectedPlugin",
]
