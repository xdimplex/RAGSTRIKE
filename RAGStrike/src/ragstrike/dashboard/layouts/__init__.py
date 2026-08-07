"""Layouts: the application shell.

The shell owns everything that is the same on every page -- the stylesheet, the sidebar, the header,
the banners, the toast queue, and the error boundary around the page body. A page renders its own
content and nothing else, which is why nine pages fit in a few hundred lines between them.
"""

from ragstrike.dashboard.layouts.page_layout import (
    inject_theme,
    page_header,
    render_banners,
    render_notifications,
    section,
)
from ragstrike.dashboard.layouts.sidebar import render_sidebar

__all__ = [
    "inject_theme",
    "page_header",
    "render_banners",
    "render_notifications",
    "render_sidebar",
    "section",
]
