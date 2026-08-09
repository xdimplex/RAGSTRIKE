"""The page registry.

WHY A REGISTRY AND NOT A MATCH STATEMENT
    Nine pages today. The sidebar, the router, the breadcrumb, the global-search "jump to" results,
    and the quick-action buttons on Home all need the same list. Written five times it drifts within
    a week; written once it cannot.

    Adding a page is one :class:`Route` entry plus one module. Nothing else changes -- which is the
    same Open/Closed property the plugin registry and the report registry already have.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class Route:
    """One page in the navigation."""

    id: str
    title: str
    icon: str
    group: str
    #: Dotted module path, imported lazily by the router. Storing the path rather than the function
    #: keeps this module free of Streamlit, so the whole registry is importable in a plain test.
    module: str
    summary: str
    #: Pages that only make sense with a backend. Rendered as disabled with an explanation when the
    #: backend is unreachable, rather than opening and failing.
    needs_backend: bool = True


#: Sidebar section order.
NAV_GROUPS: Final[tuple[str, ...]] = ("Operate", "Manage", "Analyse", "System")

ROUTES: Final[tuple[Route, ...]] = (
    Route(
        id="home",
        title="Dashboard",
        icon="◎",
        group="Operate",
        module="ragstrike.dashboard.views.home",
        summary="Posture overview, recent activity, and quick actions.",
        needs_backend=False,
    ),
    Route(
        id="scan_center",
        title="Scan Center",
        icon="▶",
        group="Operate",
        module="ragstrike.dashboard.views.scan_center",
        summary="Configure and launch a scan, then watch it run.",
    ),
    Route(
        id="targets",
        title="Targets",
        icon="◇",
        group="Manage",
        module="ragstrike.dashboard.views.targets",
        summary="Configured targets, their health, and their authorization records.",
    ),
    Route(
        id="plugins",
        title="Plugins",
        icon="⬡",
        group="Manage",
        module="ragstrike.dashboard.views.plugins",
        summary="Installed attack packs and evaluation plugins.",
    ),
    Route(
        id="reports",
        title="Reports",
        icon="▤",
        group="Analyse",
        module="ragstrike.dashboard.views.reports",
        summary="Generated reports, searchable and exportable.",
    ),
    Route(
        id="scan_history",
        title="Scan History",
        icon="◷",
        group="Analyse",
        module="ragstrike.dashboard.views.scan_history",
        summary="Every previous scan, with comparison and replay.",
    ),
    Route(
        id="system_status",
        title="System Status",
        icon="⬢",
        group="System",
        module="ragstrike.dashboard.views.system_status",
        summary="Subsystem health and host resources.",
        needs_backend=False,
    ),
    Route(
        id="settings",
        title="Settings",
        icon="⚙",
        group="System",
        module="ragstrike.dashboard.views.settings",
        summary="Dashboard preferences and the effective configuration.",
        needs_backend=False,
    ),
    Route(
        id="about",
        title="About",
        icon="◈",   # U+24D8 had no glyph in the console font and rendered as a hollow box
        group="System",
        module="ragstrike.dashboard.views.about",
        summary="What RAGStrike is, what it refuses to do, and how to cite it.",
        needs_backend=False,
    ),
)

DEFAULT_ROUTE: Final[Route] = ROUTES[0]

_BY_ID: Final[dict[str, Route]] = {route.id: route for route in ROUTES}


def route_for(page_id: str) -> Route:
    """Resolve a page id, falling back to Home.

    Falls back rather than raising: a bookmarked id from a version that had a different page should
    land the operator somewhere useful, not on a traceback.
    """
    return _BY_ID.get(page_id.strip(), DEFAULT_ROUTE)


def grouped_routes() -> list[tuple[str, list[Route]]]:
    """Routes bucketed into sidebar sections, in :data:`NAV_GROUPS` order.

    Groups with no routes are omitted, so removing the last page from a section removes the heading
    too rather than leaving an empty label.
    """
    buckets: list[tuple[str, list[Route]]] = []
    for group in NAV_GROUPS:
        members = [route for route in ROUTES if route.group == group]
        if members:
            buckets.append((group, members))
    return buckets
