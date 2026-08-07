"""Turning a page id into a rendered page.

The router imports the page module lazily and calls its ``render(ctx)``. Lazy because importing all
nine pages on every Streamlit re-run costs real milliseconds on every click, and because a syntax
error in the About page should not stop the operator reading Scan Center.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Protocol

from ragstrike.dashboard.navigation.routes import Route, route_for


class PageModule(Protocol):
    """The contract every page module satisfies. One function, one argument."""

    def render(self, context: Any) -> None:  # pragma: no cover - structural type only
        ...


@dataclass(frozen=True, slots=True)
class Resolution:
    """The outcome of resolving a page id."""

    route: Route
    render: Callable[[Any], None] | None
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.render is not None


def resolve(page_id: str, *, importer: Callable[[str], Any] = import_module) -> Resolution:
    """Find the render callable for a page id.

    ``importer`` is injected so tests can resolve against stubs -- and so a test can prove the
    failure path without shipping a deliberately broken page module.

    A page that fails to import is reported, not raised. The shell renders the error inside the
    normal layout so the sidebar still works and the operator can navigate away.
    """
    route = route_for(page_id)
    try:
        module = importer(route.module)
    except Exception as exc:  # any import failure must stay navigable
        return Resolution(route=route, render=None, error=f"{type(exc).__name__}: {exc}")

    render = getattr(module, "render", None)
    if not callable(render):
        return Resolution(
            route=route,
            render=None,
            error=f"{route.module} defines no render() function",
        )
    return Resolution(route=route, render=render)


@dataclass(frozen=True, slots=True)
class Router:
    """Stateful navigation over an :class:`~ragstrike.dashboard.state.store.AppState`.

    Holds no page list of its own -- it reads the registry -- so it cannot disagree with the sidebar
    about which pages exist.
    """

    importer: Callable[[str], Any] = import_module

    def current(self, page_id: str) -> Route:
        return route_for(page_id)

    def dispatch(self, page_id: str, context: Any) -> Resolution:
        """Resolve and render. Returns the resolution so the caller can show the error itself."""
        resolution = resolve(page_id, importer=self.importer)
        if resolution.render is not None:
            resolution.render(context)
        return resolution
