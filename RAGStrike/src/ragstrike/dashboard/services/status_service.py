"""System status: subsystem health, versions, host resources.

WHY EVERY SUBSYSTEM HAS A ROW EVEN WHEN THE BACKEND IS SILENT
    If the dashboard only rendered the ones the backend mentioned, a backend that stopped reporting
    SQLite would make SQLite *disappear* -- which reads as "fine" and means "unknown".
    :data:`SUBSYSTEMS` is the fixed list, and anything the backend omits is shown as ``unknown``
    with that word on it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ragstrike.dashboard.services.errors import (
    BackendUnavailableError,
    NotImplementedByBackendError,
)
from ragstrike.dashboard.services.models import (
    ComponentHealth,
    ResourceUsage,
    SystemStatus,
    as_str,
)
from ragstrike.dashboard.services.transport import BackendTransport

#: (payload key, display name). Order is the order they render in.
#:
#: RAGSTRIKE'S OWN SUBSYSTEMS ONLY.
#:     ChromaDB was listed here and rendered with the note "not used by the scanner; the lab targets
#:     own the vector store" -- a permanent row on the health page for a component this application
#:     does not use. A status board is a list of things that can break YOUR tool; a row that can only
#:     ever say "not mine" trains the reader to skim the board, which is the opposite of its purpose.
#:
#:     The labs have their own System Status pages, and ChromaDB belongs on those.
SUBSYSTEMS: tuple[tuple[str, str], ...] = (
    ("fastapi", "FastAPI"),
    ("ollama", "Ollama"),
    ("sqlite", "SQLite"),
    ("analyzer", "Analyzer"),
    ("reporting", "Reporting Engine"),
    ("plugin_framework", "Plugin Framework"),
    ("sdk", "SDK"),
)


@dataclass(frozen=True, slots=True)
class VersionInfo:
    """Versions the About and Status pages display."""

    engine: str = ""
    plugin_api: str = ""
    scoring_model: str = ""

    @property
    def known(self) -> bool:
        return bool(self.engine)


@dataclass(frozen=True, slots=True)
class StatusService:
    """Health for the System Status page, and the reachability probe the whole shell depends on."""

    transport: BackendTransport

    def reachable(self) -> bool:
        """Whether the backend answers at all.

        Every page asks this before it asks for anything else, so the shell can show one clear
        "backend offline" state instead of nine separate failures.
        """
        try:
            self.transport.request("GET", "/health")
        except (BackendUnavailableError, NotImplementedByBackendError):
            return False
        except Exception:  # a health check must never be the thing that crashes
            return False
        return True

    def versions(self) -> VersionInfo:
        try:
            payload = self.transport.request("GET", "/version")
        except (BackendUnavailableError, NotImplementedByBackendError):
            return VersionInfo()
        body: Mapping[str, object] = payload if isinstance(payload, Mapping) else {}
        return VersionInfo(
            engine=as_str(body, "engine"),
            plugin_api=as_str(body, "plugin_api"),
            scoring_model=as_str(body, "scoring_model"),
        )

    def status(self) -> SystemStatus:
        """The whole picture, with unknown subsystems named rather than omitted."""
        try:
            payload = self.transport.request("GET", "/health")
        except (BackendUnavailableError, NotImplementedByBackendError):
            payload = {}

        body: Mapping[str, object] = payload if isinstance(payload, Mapping) else {}
        raw_components = body.get("components")
        components_payload: Mapping[str, object] = (
            raw_components if isinstance(raw_components, Mapping) else {}
        )
        raw_resources = body.get("resources")

        components = tuple(
            ComponentHealth.from_payload(
                label,
                (
                    components_payload.get(key)  # type: ignore[arg-type]  # guarded on the next line
                    if isinstance(components_payload.get(key), Mapping)
                    else {}
                ),
            )
            for key, label in SUBSYSTEMS
        )
        versions = self.versions()
        return SystemStatus(
            components=components,
            resources=ResourceUsage.from_payload(
                raw_resources if isinstance(raw_resources, Mapping) else {}
            ),
            engine_version=versions.engine,
            plugin_api_version=versions.plugin_api,
            scoring_model_version=versions.scoring_model,
            checked_at=as_str(body, "checked_at"),
        )
