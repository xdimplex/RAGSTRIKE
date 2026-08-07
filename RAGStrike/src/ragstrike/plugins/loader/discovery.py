"""Finding plugin candidates on disk and in installed distributions.

Two mechanisms, both active (ADR-002):

* **Directory scan** -- any subdirectory of a configured plugin directory containing one of the
  supported manifest names (``metadata.yaml``, ``pack.yaml``). Drop a folder in, restart, it is
  found. This is the development and private-pack path.
* **Entry points** -- the ``ragstrike.attack_packs`` group, for ``pip install``-ed packs.

**No plugin name appears anywhere in this module, or anywhere else in the engine.** A hardcoded
list would defeat the entire subsystem, and there is a test that walks the engine's AST to prove
none exists.

This module *finds* candidates. Deciding which ones activate is policy, and policy lives in
:mod:`ragstrike.plugins.registry`.
"""

from __future__ import annotations

from collections.abc import Iterator
from importlib.metadata import entry_points
import logging
from pathlib import Path

from ragstrike.core.errors import PluginLoadError
from ragstrike.plugins.loader.manifest import PluginManifest, find_manifest, parse_manifest

log = logging.getLogger(__name__)


def discover_directories(directories: list[Path]) -> Iterator[PluginManifest]:
    """Yield a manifest for every plugin directory found under *directories*.

    A directory that fails to parse is logged and skipped, never fatal. A security tool that
    refuses to start because one optional third-party extension is malformed simply will not be
    run.
    """
    for directory in directories:
        if not directory.is_dir():
            log.debug("plugin directory absent", extra={"path": str(directory)})
            continue

        for candidate in sorted(directory.iterdir()):
            if not candidate.is_dir() or candidate.name.startswith((".", "_")):
                continue

            try:
                manifest_path = find_manifest(candidate)
            except PluginLoadError as exc:
                log.warning(
                    "plugin refused",
                    extra={"path": str(candidate), "reason": exc.message},
                )
                continue

            if manifest_path is None:
                log.debug("no manifest, skipping", extra={"path": str(candidate)})
                continue

            try:
                manifest = parse_manifest(manifest_path)
            except PluginLoadError as exc:
                log.warning(
                    "plugin manifest rejected",
                    extra={"path": str(manifest_path), "reason": exc.message},
                )
                continue

            log.debug(
                "plugin discovered",
                extra={"slug": manifest.slug, "source": str(manifest.source)},
            )
            yield manifest


def discover_entry_points(group: str) -> Iterator[tuple[str, str]]:
    """Yield ``(name, value)`` for every entry point in *group*.

    First-party packs register through this same public group, so the extension path cannot
    silently rot -- if it breaks, the shipped product breaks first.
    """
    try:
        found = entry_points(group=group)
    except Exception as exc:
        log.warning("entry point scan failed", extra={"group": group, "error": str(exc)})
        return

    for entry in found:
        log.debug("entry point discovered", extra={"name": entry.name, "value": entry.value})
        yield entry.name, entry.value
