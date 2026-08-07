"""Dashboard configuration -- read from the environment, never from the engine.

WHY THIS FILE EXISTS AT ALL
    The engine has a perfectly good configuration loader in ``ragstrike.core.config``. The dashboard
    may not import it (ADR-010, and import-linter contract 3 fails CI if it tries), so it carries its
    own tiny loader. This is duplication on purpose: it is the price of the boundary, and it is
    twenty lines rather than a subsystem.

WHAT BELONGS HERE
    Only what the *user interface* needs to start: where the backend is, how often to poll, which
    theme to open with. Engine settings -- concurrency, safety policy, plugin directories -- are the
    backend's business and are only ever *displayed* here, never sourced from here.

ENVIRONMENT
    Every field is settable as ``RAGSTRIKE_DASHBOARD__<FIELD>``, matching the variable the
    Dockerfile already documents. Nesting uses the same double underscore the engine uses, so an
    operator who has configured one has configured the other.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import os
from typing import Final, Literal

ENV_PREFIX: Final = "RAGSTRIKE_DASHBOARD__"

TransportName = Literal["http", "demo"]

#: The transports a user may ask for by name. ``http`` is the real one; ``demo`` is opt-in and
#: announces itself on every page, because unlabelled sample data in a security tool is a hazard.
TRANSPORTS: Final[tuple[TransportName, ...]] = ("http", "demo")

ThemeName = Literal["dark", "light"]
THEMES: Final[tuple[ThemeName, ...]] = ("dark", "light")

LOG_LEVELS: Final[tuple[str, ...]] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

#: Report formats the dashboard offers. Deliberately mirrors what the reporting engine ships
#: (Phase 11) rather than importing it -- the backend is the authority and the list is refreshed
#: from ``GET /version`` when a backend is reachable.
REPORT_FORMATS: Final[tuple[str, ...]] = ("html", "markdown", "json", "pdf")

#: Only these languages exist. The brief asks for a *placeholder*, and a placeholder that pretends
#: to offer twelve locales it cannot render is worse than one that admits to one.
LANGUAGES: Final[tuple[str, ...]] = ("en",)


def _env(name: str, default: str) -> str:
    return os.environ.get(f"{ENV_PREFIX}{name}", default).strip() or default


def _env_float(name: str, default: float) -> float:
    raw = _env(name, str(default))
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_choice(name: str, default: str, allowed: tuple[str, ...]) -> str:
    value = _env(name, default).lower()
    return value if value in allowed else default


@dataclass(frozen=True, slots=True)
class ReportPreferences:
    """What the Reports page defaults to. Cosmetic -- none of it changes a finding."""

    default_format: str = "html"
    include_evidence: bool = True
    redaction: str = "partial"
    open_after_export: bool = False


@dataclass(frozen=True, slots=True)
class DashboardConfig:
    """Everything the UI needs to boot.

    Frozen because a configuration that mutates while Streamlit re-runs the script is a source of
    "it worked a second ago" bugs. Session-scoped preference changes produce a *new* config via
    :meth:`with_overrides` and store it in state.
    """

    api_base_url: str = "http://127.0.0.1:8000/api/v1"
    transport: TransportName = "http"
    request_timeout_s: float = 15.0

    theme: ThemeName = "dark"
    language: str = "en"

    log_level: str = "INFO"
    default_timeout_s: float = 120.0
    default_target: str = ""

    refresh_interval_s: float = 3.0
    plugin_refresh_interval_s: float = 60.0

    reports: ReportPreferences = field(default_factory=ReportPreferences)

    @property
    def is_demo(self) -> bool:
        return self.transport == "demo"

    def with_overrides(self, **changes: object) -> DashboardConfig:
        """Return a copy. Used by the settings page; the original is never mutated."""
        return replace(self, **changes)  # type: ignore[arg-type]  # dataclasses.replace is untyped over **kwargs


def load_config() -> DashboardConfig:
    """Build the configuration from the environment, falling back to safe defaults.

    Never raises. A dashboard that refuses to start because ``REFRESH_INTERVAL`` was set to "fast"
    is a dashboard the operator cannot use to find out what went wrong.
    """
    transport = _env_choice("TRANSPORT", "http", TRANSPORTS)
    theme = _env_choice("THEME", "dark", THEMES)
    return DashboardConfig(
        api_base_url=_env("API_BASE_URL", "http://127.0.0.1:8000/api/v1").rstrip("/"),
        transport=transport,  # type: ignore[arg-type]  # _env_choice constrains to TRANSPORTS
        request_timeout_s=_env_float("REQUEST_TIMEOUT_S", 15.0),
        theme=theme,  # type: ignore[arg-type]  # _env_choice constrains to THEMES
        language=_env_choice("LANGUAGE", "en", LANGUAGES),
        log_level=_env_choice("LOG_LEVEL", "INFO", LOG_LEVELS).upper(),
        default_timeout_s=_env_float("DEFAULT_TIMEOUT_S", 120.0),
        default_target=_env("DEFAULT_TARGET", ""),
        refresh_interval_s=_env_float("REFRESH_INTERVAL_S", 3.0),
        plugin_refresh_interval_s=_env_float("PLUGIN_REFRESH_INTERVAL_S", 60.0),
        reports=ReportPreferences(
            default_format=_env_choice("REPORT_FORMAT", "html", REPORT_FORMATS),
        ),
    )


#: Field names that must never be rendered, even when a future backend starts returning them.
#: The brief's "Do not expose sensitive configuration" is enforced by
#: :func:`ragstrike.dashboard.services.settings_service.redact`, which consults this set.
SENSITIVE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "auth_token",
        "bearer",
        "credential",
        "credentials",
        "password",
        "private_key",
        "secret",
        "session_cookie",
        "token",
    }
)
