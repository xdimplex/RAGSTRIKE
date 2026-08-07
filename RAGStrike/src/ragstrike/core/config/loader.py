"""Configuration and target loading.

Precedence, lowest to highest::

    built-in defaults  ->  configs/ragstrike.yaml  ->  scan profile  ->  RAGSTRIKE_* environment
    ->  explicit overrides

THE FILE NAME, AND WHY THERE ARE TWO
    The design has named ``configs/ragstrike.yaml`` since Phase 1. The implementation read
    ``configs/config.yaml``. Both files shipped, only one was live, and the live one was the
    undocumented one -- so a user following the SDD edited a file that nothing read, got no effect
    and no error, and had no way to find out.

    Phase 16 makes the documented name the real one. ``config.yaml`` is still accepted when
    ``ragstrike.yaml`` is absent, with a ``DeprecationWarning`` and a log line naming the rename,
    because silently ignoring an existing installation's configuration would repeat the original
    mistake in the opposite direction. Support is removed at 2.0 per the deprecation policy.

Targets come from ``configs/targets.yaml``, which is a separate file because targets change far more
often than engine settings and because a target carries an authorization record that should be
reviewable on its own.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any
import warnings

from pydantic import ValidationError
import yaml

from ragstrike.core.config.models import Settings
from ragstrike.core.config.profiles import ScanProfile
from ragstrike.core.errors import ConfigurationError, TargetNotFoundError
from ragstrike.models.entities.target import Authorization, Target
from ragstrike.models.values.enums import Capability

log = logging.getLogger(__name__)

ENV_PREFIX = "RAGSTRIKE_"

#: RAGSTRIKE_SECTION__KEY -- anything shorter is not a setting (RAGSTRIKE_CONFIG_FILE and friends).
_MIN_ENV_PATH_PARTS = 2

#: Repository root: ``src/ragstrike/core/config/loader.py`` -> up five.
REPO_ROOT = Path(__file__).resolve().parents[4]


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            f"{path} is not valid YAML: {exc}", hint="Fix the syntax error and retry."
        ) from exc
    if data is not None and not isinstance(data, dict):
        raise ConfigurationError(
            f"{path} must contain a mapping at the top level, got {type(data).__name__}."
        )
    return data or {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _env_overrides() -> dict[str, Any]:
    """Collect ``RAGSTRIKE_SECTION__KEY=value`` into a nested dict.

    Values are parsed as YAML so ``RAGSTRIKE_ENGINE__MAX_CONCURRENCY=8`` arrives as an int rather
    than the string ``"8"``, which Pydantic would accept and then quietly coerce differently from
    what the YAML file would have produced.
    """
    overrides: dict[str, Any] = {}
    for env_key, raw in os.environ.items():
        if not env_key.startswith(ENV_PREFIX):
            continue
        path = env_key[len(ENV_PREFIX) :].lower().split("__")
        if len(path) < _MIN_ENV_PATH_PARTS:
            continue  # RAGSTRIKE_CONFIG_FILE and friends are not settings
        cursor = overrides
        for part in path[:-1]:
            nxt = cursor.setdefault(part, {})
            if not isinstance(nxt, dict):
                break
            cursor = nxt
        else:
            try:
                cursor[path[-1]] = yaml.safe_load(raw)
            except yaml.YAMLError:
                cursor[path[-1]] = raw
    return overrides


#: The documented file name. Read first.
CONFIG_FILENAME = "ragstrike.yaml"

#: The name the implementation used until Phase 16. Accepted, with a warning, until 2.0.
LEGACY_CONFIG_FILENAME = "config.yaml"


def resolve_config_file(root: Path) -> Path:
    """Pick the configuration file, preferring the documented name.

    Returns ``ragstrike.yaml`` when it exists. Falls back to ``config.yaml`` with a
    ``DeprecationWarning`` when only the legacy file is present, and returns the canonical path
    (which ``_read_yaml`` treats as "no file, use defaults") when neither exists.
    """
    canonical = root / "configs" / CONFIG_FILENAME
    if canonical.exists():
        return canonical

    legacy = root / "configs" / LEGACY_CONFIG_FILENAME
    if legacy.exists():
        message = (
            f"configs/{LEGACY_CONFIG_FILENAME} is deprecated; rename it to "
            f"configs/{CONFIG_FILENAME}. Support is removed in RAGStrike 2.0."
        )
        warnings.warn(message, DeprecationWarning, stacklevel=3)
        log.warning("deprecated configuration file", extra={"path": str(legacy)})
        return legacy

    return canonical


def load_settings(
    *,
    config_file: Path | None = None,
    root: Path | None = None,
    profile: ScanProfile | None = None,
    overrides: dict[str, Any] | None = None,
) -> Settings:
    """Load, merge, and validate engine configuration.

    A *profile* sits between the file and the environment: it may raise or lower engine limits for
    a deeper or shallower scan, but it cannot touch safety, storage, or plugin discovery. Depth is
    the operator's choice; the safety envelope is not.

    Raises:
        ConfigurationError: On any invalid value, naming the exact field path.
    """
    root = root or REPO_ROOT
    config_file = config_file or resolve_config_file(root)

    merged = _read_yaml(config_file)
    if profile is not None:
        engine_overrides = {
            key: value for key, value in profile.engine.model_dump().items() if value is not None
        }
        if engine_overrides:
            merged = _deep_merge(merged, {"engine": engine_overrides})
    merged = _deep_merge(merged, _env_overrides())
    if overrides:
        merged = _deep_merge(merged, overrides)

    try:
        settings = Settings.model_validate(merged)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        raise ConfigurationError(
            f"Invalid configuration in {config_file}: {problems}",
            hint="Correct the named fields and retry.",
        ) from exc

    resolved_storage = settings.storage.resolve(root)
    resolved_logging = settings.logging.model_copy(
        update={"log_dir": root / settings.logging.log_dir}
    )
    resolved_plugins = settings.plugins.model_copy(
        update={"local_dirs": [root / d for d in settings.plugins.local_dirs]}
    )
    return settings.model_copy(
        update={
            "storage": resolved_storage,
            "logging": resolved_logging,
            "plugins": resolved_plugins,
        }
    )


# -- targets --------------------------------------------------------------------------------------


def load_targets(*, targets_file: Path | None = None, root: Path | None = None) -> list[Target]:
    """Read every target from ``configs/targets.yaml``.

    Each entry supports ``name``, ``url``, ``adapter``, ``timeout``, and ``enabled``, plus an
    ``authorization`` block and adapter-specific ``options``.
    """
    root = root or REPO_ROOT
    targets_file = targets_file or root / "configs" / "targets.yaml"

    raw = _read_yaml(targets_file)
    entries = raw.get("targets") or []
    if not isinstance(entries, list):
        raise ConfigurationError(
            f"{targets_file}: 'targets' must be a list.",
            hint="Each target is a list item with at least a name, url, and adapter.",
        )

    targets: list[Target] = []
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ConfigurationError(f"{targets_file}: target #{position} is not a mapping.")
        targets.append(_build_target(entry, source=targets_file, position=position))
    return targets


def _build_target(entry: dict[str, Any], *, source: Path, position: int) -> Target:
    missing = [key for key in ("name", "url", "adapter") if not entry.get(key)]
    if missing:
        raise ConfigurationError(
            f"{source}: target #{position} is missing {', '.join(missing)}.",
            hint="Every target needs a name, a url, and an adapter.",
        )

    auth_block = entry.get("authorization") or {}
    authorization = None
    if auth_block:
        if not auth_block.get("authorized_by") or not auth_block.get("authorization_ref"):
            raise ConfigurationError(
                f"{source}: target {entry['name']!r} has an incomplete authorization block.",
                hint="Both authorized_by and authorization_ref are required.",
            )
        authorization = Authorization(
            authorized_by=str(auth_block["authorized_by"]),
            authorization_ref=str(auth_block["authorization_ref"]),
            scope=str(auth_block.get("scope", "")),
        )

    capabilities: list[Capability] = []
    for name in entry.get("capabilities") or []:
        try:
            capabilities.append(Capability(str(name).upper()))
        except ValueError as exc:
            raise ConfigurationError(
                f"{source}: target {entry['name']!r} declares unknown capability {name!r}.",
                hint=f"Valid capabilities: {', '.join(c.value for c in Capability)}.",
            ) from exc

    return Target(
        id=Target.new_id(),
        name=str(entry["name"]),
        adapter=str(entry["adapter"]),
        url=str(entry["url"]).rstrip("/"),
        timeout_s=int(entry.get("timeout", 60)),
        enabled=bool(entry.get("enabled", True)),
        authorization=authorization,
        options=dict(entry.get("options") or {}),
        capabilities=tuple(capabilities),
    )


def select_target(targets: list[Target], name: str | None) -> Target:
    """Pick the named target, or the only enabled one when no name is given.

    Raises:
        TargetNotFoundError: No match, or an ambiguous choice with no name supplied.
    """
    enabled = [t for t in targets if t.enabled]

    if name:
        for target in targets:
            if target.name == name:
                return target
        known = ", ".join(t.name for t in targets) or "none configured"
        raise TargetNotFoundError(f"No target named {name!r}.", hint=f"Available targets: {known}.")

    if not enabled:
        raise TargetNotFoundError(
            "No enabled targets configured.",
            hint="Add one to configs/targets.yaml, or set enabled: true on an existing entry.",
        )
    if len(enabled) > 1:
        names = ", ".join(t.name for t in enabled)
        raise TargetNotFoundError(
            f"{len(enabled)} enabled targets; pick one with --target.",
            hint=f"Enabled targets: {names}.",
        )
    return enabled[0]
