"""Plugin validation rules.

Framework-level checks that run at load time, before the plugin gets to run its own
:meth:`~ragstrike.plugins.base.attack.BaseAttack.validate`. Both are combined in the registry;
either failing means the plugin is rejected.

The rules here are deliberately minimal and structural: does the folder exist, does the manifest
name a real file, does the class actually descend from ``BaseAttack``. Semantic checks (payload
non-emptiness, detector coverage, category correctness) are the plugin's own job and go in the
plugin's :meth:`validate`.

Every rule returns a :class:`~ragstrike.plugins.base.reports.Check` so the CLI's
``ragstrike plugins validate`` can render them uniformly.
"""

from __future__ import annotations

import logging
from pathlib import Path

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from ragstrike.plugins.base.attack import BaseAttack
from ragstrike.plugins.base.reports import Check, ValidationReport
from ragstrike.plugins.loader.manifest import MANIFEST_NAMES, PluginManifest

log = logging.getLogger(__name__)

#: A pack must ship its test cases, in ONE of the two shapes the framework supports.
#:
#: ``payloads/`` is the common one: a list of attack strings sent at the target. ``datasets/`` is the
#: other, used by read-only evaluation packs -- ``context-poisoning`` declares question/expectation
#: datasets and never writes to the target, so it has no payloads to ship and never will.
#:
#: This was ``("payloads",)``, and nothing enforced it: `validate_structure` had no caller. Wiring it
#: to the Validate button made it live, and it immediately reported `context-poisoning` -- a pack
#: that loads, runs, and is central to the differential -- as FAILING validation. The rule was
#: narrower than the framework it described.
CASE_DIRS = ("payloads", "datasets")
OPTIONAL_DIRS = ("tests", "examples", "docs", "assets", "schemas")


def validate_structure(plugin_dir: Path) -> ValidationReport:
    """Check the on-disk layout of a plugin directory.

    Runs before any Python is imported. A failing report here is what "the framework rejects
    malformed plugins" concretely means -- the plugin never reaches the loader.
    """
    checks: list[Check] = []

    checks.append(
        Check(
            rule="folder-exists",
            passed=plugin_dir.is_dir(),
            detail="" if plugin_dir.is_dir() else f"{plugin_dir} is not a directory.",
        )
    )
    if not plugin_dir.is_dir():
        return ValidationReport(checks=checks)

    manifest_present = any((plugin_dir / name).is_file() for name in MANIFEST_NAMES)
    checks.append(
        Check(
            rule="manifest-exists",
            passed=manifest_present,
            detail=(
                ""
                if manifest_present
                else f"none of {', '.join(MANIFEST_NAMES)} found in {plugin_dir.name}."
            ),
        )
    )

    present = [name for name in CASE_DIRS if (plugin_dir / name).is_dir()]
    checks.append(
        Check(
            rule="has-cases",
            passed=bool(present),
            detail=(
                f"ships {', '.join(present)}/"
                if present
                else f"a pack must ship one of: {', '.join(f'{d}/' for d in CASE_DIRS)}."
            ),
        )
    )

    return ValidationReport(checks=checks)


def validate_manifest(manifest: PluginManifest, *, api_version: str) -> ValidationReport:
    """Check the parsed manifest's contents.

    Split from :func:`validate_structure` because the CLI's ``validate`` command runs both, and
    the split lets the CLI report which stage refused the plugin.
    """
    checks = [
        Check(
            rule="slug-non-empty",
            passed=bool(manifest.slug),
            detail="" if manifest.slug else "plugin.slug is required.",
        ),
        Check(
            rule="version-non-empty",
            passed=bool(manifest.version),
            detail="",
        ),
        Check(
            rule="entry-point-shape",
            passed=":" in manifest.entry_point,
            detail="" if ":" in manifest.entry_point else "entry_point must be 'module:ClassName'.",
        ),
    ]

    try:
        Version(manifest.version)
        checks.append(Check(rule="version-parseable", passed=True))
    except InvalidVersion:
        checks.append(
            Check(
                rule="version-parseable",
                passed=False,
                detail=f"version {manifest.version!r} is not a valid SemVer.",
            )
        )

    try:
        compatible = Version(api_version) in SpecifierSet(manifest.requires_api)
        checks.append(
            Check(
                rule="api-compatible",
                passed=compatible,
                detail=(
                    ""
                    if compatible
                    else f"requires plugin API {manifest.requires_api}; engine is {api_version}."
                ),
            )
        )
    except (InvalidSpecifier, InvalidVersion) as exc:
        checks.append(
            Check(
                rule="api-compatible",
                passed=False,
                detail=f"requires_api {manifest.requires_api!r} is not a valid SemVer range: {exc}",
            )
        )

    return ValidationReport(checks=checks)


def validate_class(attack_class: type) -> ValidationReport:
    """Check the loaded class satisfies the ``BaseAttack`` contract.

    Runs after import, before instantiation. A class that fails here would have crashed at first
    use with a less helpful error.
    """
    checks: list[Check] = []

    inherits = isinstance(attack_class, type) and issubclass(attack_class, BaseAttack)
    checks.append(
        Check(
            rule="inherits-base-attack",
            passed=inherits,
            detail="" if inherits else f"{attack_class!r} does not subclass BaseAttack.",
        )
    )
    if not inherits:
        return ValidationReport(checks=checks)

    required_methods = ("payloads", "execute", "analyze", "recommendation")
    for method in required_methods:
        # abstractmethods that were not overridden are visible on __abstractmethods__.
        overridden = method not in getattr(attack_class, "__abstractmethods__", set())
        checks.append(
            Check(
                rule=f"implements-{method}",
                passed=overridden,
                detail="" if overridden else f"{attack_class.__name__} must implement {method}().",
            )
        )

    return ValidationReport(checks=checks)
