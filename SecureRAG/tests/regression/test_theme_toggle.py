"""The lab UI is LIGHT, always, and has no theme control.

WHY THE TOGGLE WAS DELETED RATHER THAN FIXED AGAIN
    "Half light, half dark" was reported five times. It was fixed twice -- once by adding CSS
    specificity, once by driving Streamlit's own base theme -- and reported again after each.

    The cause was never a single selector. Streamlit compiles its base theme into every native
    widget it renders, so supporting a second theme means keeping a hand-written stylesheet in step
    with a compiled one, across every widget and every Streamlit release. Each fix closed the gap
    for the widgets someone had thought of, and the next release or the next widget reopened it.

    Removing the choice removes the class of bug: a page that can only be light cannot be half dark.

WHY LIGHT FOR THE LABS
    They impersonate ordinary business chat applications, which is what makes them useful targets.
    It also tells them apart at a glance from the dark console that attacks them.

    This file previously asserted the toggle worked. That it passed while the UI was visibly broken
    is the reason it now asserts the opposite.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend"

PAGES = [FRONTEND / "app.py", *sorted((FRONTEND / "pages").glob("*.py"))]

_TIMEOUT_S = 90


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_every_page_loads(page: Path) -> None:
    app = AppTest.from_file(str(page), default_timeout=_TIMEOUT_S)
    app.run()

    assert not app.exception, [e.message for e in app.exception]


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_no_page_offers_a_theme_control(page: Path) -> None:
    """No toggle, no checkbox, no selectbox that could put the UI into a second theme."""
    app = AppTest.from_file(str(page), default_timeout=_TIMEOUT_S)
    app.run()

    labels = [w.label for w in (*app.toggle, *app.checkbox, *app.selectbox)]
    offending = [label for label in labels if "theme" in str(label).lower()]
    assert not offending, f"{page.name} still offers a theme control: {offending}"


def test_the_toggle_renderer_is_gone() -> None:
    """Pinned as a fact: leaving the function behind invites a page to call it again."""
    from frontend import theme

    assert not hasattr(theme, "render_theme_toggle")


def test_the_palette_is_light_and_not_configurable() -> None:
    """`apply` ignores any stored preference. A hand-edited URL cannot produce a dark lab."""
    from frontend import theme

    palette = theme.apply(settings=None)

    assert palette.name == "light"
    assert palette is theme.LIGHT
