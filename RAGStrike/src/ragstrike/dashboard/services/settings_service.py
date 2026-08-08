"""Settings: session preferences, and the effective configuration, redacted.

TWO KINDS OF SETTING, DELIBERATELY NOT MIXED
    *Dashboard preferences* -- theme, refresh intervals, default target, report defaults -- belong to
    this session and change immediately. They never affect what a scan does.

    *Engine configuration* -- concurrency, safety policy, plugin directories -- belongs to the
    backend and is shown **read-only**. A UI that could edit the safety policy would be a UI that
    could turn off the thing stopping an operator scanning a system they are not authorized to
    scan, and no amount of confirmation dialog makes that a good idea.

"DO NOT EXPOSE SENSITIVE CONFIGURATION"
    :func:`redact` is the enforcement, and it works on key *names* rather than on a list of known
    fields -- so a backend that starts returning ``ollama_api_key`` tomorrow is redacted today,
    without anyone remembering to add it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Any

from ragstrike.dashboard.config import (
    LANGUAGES,
    LOG_LEVELS,
    REPORT_FORMATS,
    SENSITIVE_KEYS,
    THEMES,
    DashboardConfig,
)
from ragstrike.dashboard.services.transport import BackendTransport

REDACTED = "••••••••"


def is_sensitive(key: str) -> bool:
    """Whether a configuration key must never be rendered.

    Substring matching on a lowercased key: ``OLLAMA_API_KEY``, ``db.password``, and
    ``headers.Authorization`` all match, which is the point. False positives cost one hidden value;
    a false negative puts a credential on a screen someone is about to screenshot.
    """
    lowered = key.strip().lower()
    return any(marker in lowered for marker in SENSITIVE_KEYS)


def redact(config: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively replace sensitive values with :data:`REDACTED`."""
    cleaned: dict[str, Any] = {}
    for key, value in config.items():
        name = str(key)
        if is_sensitive(name):
            cleaned[name] = REDACTED
        elif isinstance(value, Mapping):
            cleaned[name] = redact(value)
        elif isinstance(value, list):
            cleaned[name] = [redact(v) if isinstance(v, Mapping) else v for v in value]
        else:
            cleaned[name] = value
    return cleaned


@dataclass(frozen=True, slots=True)
class SettingsOption:
    """One editable preference, described so the page can render it without a per-field branch."""

    key: str
    label: str
    kind: str
    choices: tuple[str, ...] = ()
    help: str = ""
    minimum: float = 0.0
    maximum: float = 0.0


#: The editable surface. Adding a preference is an entry here plus a field on
#: :class:`~ragstrike.dashboard.config.DashboardConfig` -- the settings page itself does not change.
OPTIONS: tuple[SettingsOption, ...] = (
    SettingsOption("theme", "Theme", "choice", THEMES, "Applies immediately to this session."),
    SettingsOption(
        "language",
        "Language",
        "choice",
        LANGUAGES,
        "Placeholder. Only English is implemented; the string catalog is not localized yet.",
    ),
    SettingsOption(
        "log_level",
        "Log level",
        "choice",
        LOG_LEVELS,
        "Filters the log viewer. Does not change what the engine writes to disk.",
    ),
    SettingsOption("default_timeout_s", "Default timeout", "number", (), "Seconds.", 5.0, 900.0),
    SettingsOption("default_target", "Default target", "text", (), "Preselected in Scan Center."),
    SettingsOption(
        "refresh_interval_s", "Dashboard refresh", "number", (), "Seconds between polls.", 1.0, 60.0
    ),
    SettingsOption(
        "plugin_refresh_interval_s",
        "Plugin refresh",
        "number",
        (),
        "Seconds between plugin inventory refreshes.",
        5.0,
        600.0,
    ),
)

REPORT_OPTIONS: tuple[SettingsOption, ...] = (
    SettingsOption("default_format", "Default report format", "choice", REPORT_FORMATS),
    SettingsOption("include_evidence", "Include evidence", "bool"),
    SettingsOption(
        "redaction",
        "Redaction",
        "choice",
        ("none", "partial", "full"),
        "Applied by the reporting engine, not here.",
    ),
)


@dataclass(frozen=True, slots=True)
class SettingsService:
    """Reads and writes preferences; only ever reads engine configuration."""

    transport: BackendTransport

    def effective_config(self, config: DashboardConfig) -> dict[str, Any]:
        """The dashboard's own configuration, redacted, for display."""
        rendered: dict[str, Any] = {}
        for spec in fields(config):
            value = getattr(config, spec.name)
            if hasattr(value, "__dataclass_fields__"):
                rendered[spec.name] = redact(
                    {f.name: getattr(value, f.name) for f in fields(value)}
                )
            else:
                rendered[spec.name] = REDACTED if is_sensitive(spec.name) else value
        return redact(rendered)

    @staticmethod
    def apply(config: DashboardConfig, changes: Mapping[str, Any]) -> DashboardConfig:
        """Apply preference changes, ignoring keys that are not preferences.

        Ignoring rather than raising: the settings form posts whatever widgets it rendered, and a
        stale widget key from a previous version should not stop the other seven settings saving.
        """
        known = {spec.name for spec in fields(config)}
        accepted = {k: v for k, v in changes.items() if k in known and k != "reports"}
        return config.with_overrides(**accepted) if accepted else config
