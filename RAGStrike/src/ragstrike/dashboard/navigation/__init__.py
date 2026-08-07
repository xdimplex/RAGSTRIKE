"""Routing: the page registry and the resolver that turns a page id into a render call."""

from ragstrike.dashboard.navigation.router import Router, resolve
from ragstrike.dashboard.navigation.routes import (
    DEFAULT_ROUTE,
    NAV_GROUPS,
    ROUTES,
    Route,
    grouped_routes,
    route_for,
)

__all__ = [
    "DEFAULT_ROUTE",
    "NAV_GROUPS",
    "ROUTES",
    "Route",
    "Router",
    "grouped_routes",
    "resolve",
    "route_for",
]
