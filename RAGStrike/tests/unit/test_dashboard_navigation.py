"""Navigation tests.

THE CLAIM UNDER TEST: **there is one source of truth for what pages exist.**

The sidebar, the router, the quick actions on Home, and the global-search "jump to" results all need
the same page list. Written four times it drifts within a week. These tests pin that it is written
once, that every registered page actually resolves, and that a page which fails to import leaves the
operator able to navigate away from it rather than taking the whole app down.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from ragstrike.dashboard.navigation.router import Resolution, Router, resolve
import ragstrike.dashboard.navigation.routes as routes_module
from ragstrike.dashboard.navigation.routes import (
    DEFAULT_ROUTE,
    NAV_GROUPS,
    ROUTES,
    grouped_routes,
    route_for,
)

#: The nine the brief names.
EXPECTED_PAGES = {
    "home",
    "scan_center",
    "targets",
    "plugins",
    "reports",
    "scan_history",
    "settings",
    "system_status",
    "about",
}


# -- the registry ----------------------------------------------------------------------------------


def test_the_nine_pages_the_brief_names_are_all_registered() -> None:
    assert {route.id for route in ROUTES} == EXPECTED_PAGES


def test_no_page_id_is_registered_twice() -> None:
    """A duplicate would make ``route_for`` return whichever came last, silently."""
    ids = [route.id for route in ROUTES]

    assert len(ids) == len(set(ids))


def test_every_route_declares_a_module_under_the_views_package() -> None:
    assert all(route.module.startswith("ragstrike.dashboard.views.") for route in ROUTES)


def test_there_is_no_pages_directory_beside_the_streamlit_entry_point() -> None:
    """The view modules must NOT live in a directory called ``pages``.

    Streamlit treats any ``pages/`` directory sitting next to the entry script as a multipage app
    and builds its own sidebar nav from the filenames -- no opt-out. This dashboard deliberately
    renders navigation from the route registry instead (see ``layouts/sidebar.py``), so while the
    package was named ``pages`` the operator saw TWO navigation lists: the real one, and an
    auto-generated one whose entries executed each view module standalone, with no router, no
    context, and no services. That second list looked like a broken half of the product.

    The directory name is the entire mechanism, so the name is what this test pins.
    """
    entry_point = Path(routes_module.__file__).resolve().parents[1]  # .../dashboard

    assert not (entry_point / "pages").exists(), (
        "dashboard/pages/ would make Streamlit auto-generate a second, non-functional nav; "
        "the view modules belong in dashboard/views/"
    )


def test_every_route_has_a_summary() -> None:
    """It is the tooltip and the search subtitle. An empty one is a blank tooltip."""
    assert all(route.summary for route in ROUTES)


def test_every_route_belongs_to_a_declared_group() -> None:
    """A route in an unlisted group would vanish from the sidebar without any error."""
    assert {route.group for route in ROUTES} <= set(NAV_GROUPS)


def test_grouping_covers_every_route_exactly_once() -> None:
    grouped = [route.id for _, routes in grouped_routes() for route in routes]

    assert sorted(grouped) == sorted(EXPECTED_PAGES)


def test_grouping_follows_the_declared_group_order() -> None:
    order = [group for group, _ in grouped_routes()]

    assert order == [group for group in NAV_GROUPS if group in order]


def test_empty_groups_are_omitted_rather_than_rendered_as_bare_headings() -> None:
    assert all(routes for _, routes in grouped_routes())


def test_the_pages_that_work_offline_are_the_ones_that_have_nothing_to_fetch() -> None:
    """Home, Settings, System Status, and About stay reachable with no backend -- System Status
    because "is the backend down" is precisely what it is for."""
    offline = {route.id for route in ROUTES if not route.needs_backend}

    assert offline == {"home", "settings", "system_status", "about"}


# -- resolution ------------------------------------------------------------------------------------


def test_an_unknown_page_id_lands_on_home_rather_than_raising() -> None:
    """A bookmarked id from a version with different pages should land somewhere useful."""
    assert route_for("no-such-page") is DEFAULT_ROUTE
    assert DEFAULT_ROUTE.id == "home"


def test_a_page_id_is_matched_after_stripping_whitespace() -> None:
    assert route_for("  reports  ").id == "reports"


@pytest.mark.parametrize("route", ROUTES, ids=lambda route: route.id)
def test_every_registered_page_actually_resolves(route: Any) -> None:
    """The registry is only a source of truth if the modules behind it exist. A typo'd module path
    would otherwise surface as a broken page in production."""
    resolution = resolve(route.id)

    assert resolution.ok, resolution.error


@pytest.mark.parametrize("route", ROUTES, ids=lambda route: route.id)
def test_every_page_exposes_a_single_render_entry_point(route: Any) -> None:
    module = __import__(route.module, fromlist=["render"])

    assert callable(module.render)


# -- failure paths ---------------------------------------------------------------------------------


def test_a_page_that_fails_to_import_is_reported_not_raised() -> None:
    """Without this the exception takes out the whole Streamlit script -- sidebar included -- and
    the operator cannot navigate away from the broken page."""

    def explode(_name: str) -> Any:
        raise ImportError("no module named pandas")

    resolution = resolve("reports", importer=explode)

    assert not resolution.ok
    assert "ImportError" in resolution.error
    assert resolution.route.id == "reports"


def test_a_module_without_render_is_reported_as_such() -> None:
    resolution = resolve("reports", importer=lambda _name: SimpleNamespace())

    assert not resolution.ok
    assert "render" in resolution.error


def test_a_non_callable_render_is_refused() -> None:
    resolution = resolve("reports", importer=lambda _name: SimpleNamespace(render="not a function"))

    assert not resolution.ok


# -- the router ------------------------------------------------------------------------------------


def test_dispatch_calls_the_page_with_the_context() -> None:
    seen: list[object] = []
    module = SimpleNamespace(render=seen.append)
    router = Router(importer=lambda _name: module)
    context = object()

    resolution = router.dispatch("home", context)

    assert resolution.ok
    assert seen == [context]


def test_dispatch_of_a_broken_page_does_not_raise() -> None:
    def explode(_name: str) -> Any:
        raise RuntimeError("boom")

    resolution = Router(importer=explode).dispatch("home", object())

    assert not resolution.ok
    assert "RuntimeError" in resolution.error


def test_the_router_reads_the_registry_rather_than_its_own_list() -> None:
    """Two lists of pages is the drift the registry exists to prevent."""
    assert Router().current("plugins") is route_for("plugins")


def test_a_resolution_without_a_render_is_not_ok() -> None:
    assert not Resolution(route=DEFAULT_ROUTE, render=None, error="x").ok
