"""``plugins.yaml`` -- per-plugin runtime configuration.

Two things this file controls, and only these two:

**Operational overrides.** ``enabled``, ``timeout``, ``severity_override``. An operator can
disable a plugin without editing its manifest, cap its runtime, or raise its severity for a
specific scan profile.

**Plugin-supplied configuration.** Free-form ``config:`` block passed into the plugin's
``PluginContext``. A plugin declares a schema for it (Phase 5's SDK will validate) and reads it
via ``self.context.config``.

**No security controls live here.** The manifest declares what a plugin needs; ``plugins.yaml``
tunes it. Neither can grant a plugin more than the framework already permits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any

import yaml

from ragstrike.core.errors import ConfigurationError

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PluginRuntimeConfig:
    """Runtime overrides for one plugin."""

    enabled: bool | None = None
    timeout_s: int | None = None
    severity_override: str | None = None
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PluginConfigStore:
    """The whole ``plugins.yaml``, indexed by slug.

    Mutable because the CLI's ``enable``/``disable`` write back into it. The mutation surface is
    intentionally narrow: only the four fields on :class:`PluginRuntimeConfig`.
    """

    path: Path
    entries: dict[str, PluginRuntimeConfig] = field(default_factory=dict)

    # -- reads ------------------------------------------------------------------------------

    def for_plugin(self, slug: str) -> PluginRuntimeConfig:
        """Return the config for *slug*, or the empty default if none is set."""
        return self.entries.get(slug, PluginRuntimeConfig())

    def is_disabled(self, slug: str) -> bool:
        entry = self.entries.get(slug)
        return entry is not None and entry.enabled is False

    def slugs(self) -> list[str]:
        return sorted(self.entries)

    # -- writes -----------------------------------------------------------------------------

    def set_enabled(self, slug: str, enabled: bool) -> None:
        """Change enablement for *slug*. In memory only; call :meth:`save` to persist."""
        current = self.entries.get(slug, PluginRuntimeConfig())
        self.entries[slug] = PluginRuntimeConfig(
            enabled=enabled,
            timeout_s=current.timeout_s,
            severity_override=current.severity_override,
            config=current.config,
        )

    def save(self) -> None:
        """Write the store back to disk, preserving the file's shape.

        Absent fields stay absent -- so a plugin whose only override is ``enabled: false`` does
        not gain empty ``timeout``/``severity_override`` fields it never declared.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)

        payload: dict[str, Any] = {"version": 1, "plugins": {}}
        for slug in sorted(self.entries):
            entry = self.entries[slug]
            block: dict[str, Any] = {}
            if entry.enabled is not None:
                block["enabled"] = entry.enabled
            if entry.timeout_s is not None:
                block["timeout"] = entry.timeout_s
            if entry.severity_override is not None:
                block["severity_override"] = entry.severity_override
            if entry.config:
                block["config"] = entry.config
            payload["plugins"][slug] = block

        self.path.write_text(
            yaml.safe_dump(payload, sort_keys=True, default_flow_style=False),
            encoding="utf-8",
        )
        log.info("plugins config saved", extra={"path": str(self.path)})


def load_plugin_config(path: Path) -> PluginConfigStore:
    """Read ``plugins.yaml``. A missing file is not an error -- most operators never edit one.

    Raises:
        ConfigurationError: The file exists but is malformed. The scanner will not start with a
            silently ignored plugins config, because an ignored disable is the difference between
            "we skipped this attack" and "we ran it and it passed" -- opposite claims about
            security posture.
    """
    store = PluginConfigStore(path=path)
    if not path.exists():
        return store

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            f"{path} is not valid YAML: {exc}", hint="Fix the syntax and retry."
        ) from exc

    if raw is None:
        return store
    if not isinstance(raw, dict):
        raise ConfigurationError(f"{path}: expected a mapping at the top level.")

    plugins = raw.get("plugins") or {}
    if not isinstance(plugins, dict):
        raise ConfigurationError(
            f"{path}: 'plugins' must be a mapping keyed by slug.",
            hint="See configs/plugins.yaml for the expected shape.",
        )

    for slug, entry in plugins.items():
        if entry is None:
            continue
        if not isinstance(entry, dict):
            raise ConfigurationError(
                f"{path}: plugin {slug!r} entry must be a mapping, got {type(entry).__name__}."
            )
        store.entries[str(slug)] = PluginRuntimeConfig(
            enabled=_optional_bool(entry.get("enabled")),
            timeout_s=_optional_int(entry.get("timeout")),
            severity_override=_optional_str(entry.get("severity_override")),
            config=dict(entry.get("config") or {}),
        )

    log.debug("plugins config loaded", extra={"path": str(path), "plugins": list(store.entries)})
    return store


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
