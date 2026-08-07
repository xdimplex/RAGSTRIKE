"""The service layer: the dashboard's only route to the engine.

RULE
    Services never contain UI, and pages never contain a request. A page that formats a badge is
    doing its job; a page that knows a URL path is not. That split is what makes the whole interface
    testable without a browser and replaceable without touching the backend.

WIRING
    :class:`Services` is the container. One transport, seven services, built once per session and
    kept in state. Constructing it is the only place the transport choice is made.
"""

from dataclasses import dataclass

from ragstrike.dashboard.config import DashboardConfig
from ragstrike.dashboard.services.history_service import HistoryService, ScanComparison
from ragstrike.dashboard.services.plugin_service import (
    PluginInventory,
    PluginService,
    ValidationReport,
)
from ragstrike.dashboard.services.report_service import RenderedReport, ReportService
from ragstrike.dashboard.services.scan_service import (
    ScanProfile,
    ScanRequest,
    ScanService,
    should_poll,
)
from ragstrike.dashboard.services.search import SearchSource, search
from ragstrike.dashboard.services.settings_service import SettingsService
from ragstrike.dashboard.services.status_service import StatusService
from ragstrike.dashboard.services.target_service import TargetService
from ragstrike.dashboard.services.transport import BackendTransport, build_transport


@dataclass(frozen=True, slots=True)
class Services:
    """Every service, sharing one transport."""

    transport: BackendTransport
    scans: ScanService
    plugins: PluginService
    targets: TargetService
    reports: ReportService
    settings: SettingsService
    status: StatusService
    history: HistoryService

    @property
    def is_demo(self) -> bool:
        return self.transport.name == "demo"

    def search_sources(self) -> list[SearchSource]:
        """The five collections global search covers.

        Built here rather than in the search module so that search knows nothing about services and
        services know nothing about search -- either can be replaced without touching the other.
        """
        return [
            SearchSource(
                kind="target",
                fetch=self.targets.list_targets,
                fields=("name", "id", "url", "adapter"),
                title_field="name",
                subtitle_field="url",
            ),
            SearchSource(
                kind="plugin",
                fetch=lambda: self.plugins.inventory().all,
                fields=("slug", "name", "category", "description"),
                title_field="display_name",
                subtitle_field="category",
                id_field="slug",
            ),
            SearchSource(
                kind="report",
                fetch=self.reports.list_reports,
                fields=("id", "scan_id", "target", "fmt"),
                title_field="id",
                subtitle_field="target",
            ),
            SearchSource(
                kind="scan",
                fetch=self.history.list_scans,
                fields=("id", "name", "target", "profile"),
                title_field="id",
                subtitle_field="target",
            ),
        ]

    def close(self) -> None:
        self.transport.close()


def build_services(config: DashboardConfig) -> Services:
    """Wire one transport into all seven services."""
    transport = build_transport(config)
    return build_services_with(transport)


def build_services_with(transport: BackendTransport) -> Services:
    """Wire an already-built transport.

    The seam every test uses: hand it a fake and the whole dashboard runs against it, with no
    network, no server, and no monkeypatching.
    """
    return Services(
        transport=transport,
        scans=ScanService(transport),
        plugins=PluginService(transport),
        targets=TargetService(transport),
        reports=ReportService(transport),
        settings=SettingsService(transport),
        status=StatusService(transport),
        history=HistoryService(transport),
    )


__all__ = [
    "BackendTransport",
    "HistoryService",
    "PluginInventory",
    "PluginService",
    "RenderedReport",
    "ReportService",
    "ScanComparison",
    "ScanProfile",
    "ScanRequest",
    "ScanService",
    "SearchSource",
    "Services",
    "SettingsService",
    "StatusService",
    "TargetService",
    "ValidationReport",
    "build_services",
    "build_services_with",
    "build_transport",
    "search",
    "should_poll",
]
