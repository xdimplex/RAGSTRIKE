"""Plugin manifest parsing.

The manifest is read **before any plugin code is imported** (ADR-003). Compatibility, declared
permissions, and the full metadata schema are checked against the file, and only then does the
loader import the module named by ``entry_point``.

Two filenames are accepted, in this precedence order:

* ``metadata.yaml`` -- Phase 4 canonical name.
* ``pack.yaml`` -- Phase 3 name, kept so existing plugins keep loading without a rename.

If both exist in the same directory the loader refuses the plugin -- two manifests are one too
many, and silent precedence would let a stale copy shadow the intended one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ragstrike.core.errors import PluginLoadError

#: Filenames the loader accepts, in preference order.
MANIFEST_NAMES: tuple[str, ...] = ("metadata.yaml", "pack.yaml")


@dataclass(frozen=True, slots=True)
class PluginPermissions:
    """Least-privilege declaration.

    v1 does not sandbox at the OS level, and says so plainly rather than implying otherwise.
    Declaring permissions makes intent auditable and lets the loader refuse elevated requests
    unless the operator opted in. Subprocess isolation is a roadmap item, not a current claim.
    """

    network_egress: bool = False
    filesystem_write: bool = False

    @property
    def is_elevated(self) -> bool:
        return self.network_egress or self.filesystem_write

    def describe(self) -> str:
        asked = [
            name
            for name, wanted in (
                ("network egress", self.network_egress),
                ("filesystem write", self.filesystem_write),
            )
            if wanted
        ]
        return ", ".join(asked) if asked else "none"


@dataclass(frozen=True, slots=True)
class PluginManifest:
    """Everything the registry knows before importing anything."""

    slug: str
    name: str
    version: str
    entry_point: str
    source: Path
    #: The manifest file itself. Retained so the CLI can point at it in a diagnostic.
    manifest_path: Path
    description: str = ""
    author: str = ""
    category: str = "uncategorized"
    requires_api: str = ">=1.0,<2.0"
    permissions: PluginPermissions = field(default_factory=PluginPermissions)
    #: Free-form plugin-supplied options, from ``metadata.yaml``. ``plugins.yaml`` overrides these.
    options: dict[str, Any] = field(default_factory=dict)
    #: Extended metadata (Phase 4). Everything below is optional and defaults to empty.
    owasp_mapping: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    required_target_type: str = "any"
    min_framework_version: str = "0.3.0"
    license: str = ""
    severity: str = "INFO"

    @property
    def module_path(self) -> str:
        """``package.module`` half of ``entry_point``."""
        return self.entry_point.split(":", 1)[0]

    @property
    def class_name(self) -> str:
        """``ClassName`` half of ``entry_point``."""
        _, _, name = self.entry_point.partition(":")
        return name


def find_manifest(plugin_dir: Path) -> Path | None:
    """Locate the manifest inside *plugin_dir*, respecting the preference order.

    Returns ``None`` if none is present. Raises :class:`PluginLoadError` if both are present in
    the same directory -- two manifests is a configuration accident, not a supported layout.
    """
    present = [plugin_dir / name for name in MANIFEST_NAMES if (plugin_dir / name).is_file()]
    if len(present) > 1:
        raise PluginLoadError(
            f"{plugin_dir}: both {' and '.join(p.name for p in present)} exist. " f"Keep one.",
            hint="metadata.yaml is preferred; rename or delete the other.",
        )
    return present[0] if present else None


def parse_manifest(path: Path) -> PluginManifest:
    """Read and validate one manifest file.

    Raises:
        PluginLoadError: The file is unreadable, malformed, or missing a required field.
    """
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise PluginLoadError(
            f"Could not read {path}: {exc}", hint="Fix the manifest, or remove the directory."
        ) from exc

    if not isinstance(raw, dict):
        raise PluginLoadError(f"{path} must contain a mapping at the top level.")

    # Accept 'plugin', 'pack', and 'metadata' as the identity section. The framework prefers
    # 'plugin'; the others are kept for backwards compatibility.
    plugin = raw.get("plugin") or raw.get("pack") or raw.get("metadata")
    if not isinstance(plugin, dict):
        raise PluginLoadError(
            f"{path} has no 'plugin' section.",
            hint="A manifest needs a 'plugin' mapping with slug, version, and entry_point.",
        )

    missing = [key for key in ("slug", "version", "entry_point") if not plugin.get(key)]
    if missing:
        raise PluginLoadError(
            f"{path}: plugin section is missing {', '.join(missing)}.",
            hint="slug, version, and entry_point are required.",
        )

    entry_point = str(plugin["entry_point"])
    if ":" not in entry_point:
        raise PluginLoadError(
            f"{path}: entry_point must be 'module:ClassName', got {entry_point!r}.",
        )

    compat = raw.get("compatibility") or {}
    perms = raw.get("permissions") or {}

    return PluginManifest(
        slug=str(plugin["slug"]),
        name=str(plugin.get("name", plugin["slug"])),
        version=str(plugin["version"]),
        entry_point=entry_point,
        source=path.parent,
        manifest_path=path,
        description=str(plugin.get("description", "")),
        author=str(plugin.get("author", "")),
        category=str(plugin.get("category", "uncategorized")),
        severity=str(plugin.get("severity", "INFO")).upper(),
        requires_api=str(compat.get("ragstrike_api", ">=1.0,<2.0")),
        min_framework_version=str(compat.get("min_framework_version", "0.3.0")),
        required_target_type=str(plugin.get("required_target_type", "any")),
        owasp_mapping=_as_tuple(plugin.get("owasp_mapping") or plugin.get("owasp_llm")),
        references=_as_tuple(plugin.get("references")),
        tags=_as_tuple(plugin.get("tags")),
        license=str(plugin.get("license", "")),
        permissions=PluginPermissions(
            network_egress=bool(perms.get("network_egress", False)),
            filesystem_write=bool(perms.get("filesystem_write", False)),
        ),
        options=dict(raw.get("options") or {}),
    )


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)
