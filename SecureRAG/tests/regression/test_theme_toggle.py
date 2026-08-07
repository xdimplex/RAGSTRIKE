"""The dark/light toggle must not crash the page it is drawn on.

WHY THIS FILE EXISTS
    Every page of both labs crashed on load with::

        StreamlitAPIException: `st.session_state.lab.theme` cannot be modified after the
        widget with key `lab.theme` is instantiated.

    One name was doing two jobs. ``lab.theme`` was the key of the ``st.toggle`` widget *and* the
    session key the preference store writes to -- so ``remember("theme", …)``, called immediately
    after the widget was drawn, was always writing to a locked key. Streamlit seals a widget's key
    the moment the widget renders, so no ordering of those two lines could have worked. The widget
    key and the preference key had to become different names.

    The toggle was reported as "not working" rather than "crashing", which is worth noting: the
    exception renders inside the page body, so from the browser it looks like a dead switch.

WHY IT DRIVES THE REAL PAGES
    Importing ``theme.py`` and calling ``render_theme_toggle`` by hand would not reproduce this.
    The failure needs a live ScriptRunContext, a real widget registration, and a second script run
    -- which is exactly what ``AppTest`` provides. A unit test here would have passed throughout.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend"

#: Every page that draws the toggle. All of them crashed, so all of them are checked.
PAGES = [
    FRONTEND / "app.py",
    *sorted((FRONTEND / "pages").glob("*.py")),
]

#: The preference key. Deliberately asserted as *different* from the widget key below -- that
#: difference is the fix, and a future refactor collapsing them would restore the crash.
PREF_KEY = "lab.theme"
WIDGET_KEY = "lab.theme.toggle"

_TIMEOUT_S = 90


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_every_page_loads_with_the_toggle(page: Path) -> None:
    app = AppTest.from_file(str(page), default_timeout=_TIMEOUT_S)
    app.run()

    assert not app.exception, [e.message for e in app.exception]
    assert any(t.label == "Dark theme" for t in app.sidebar.toggle), "toggle missing from sidebar"


def test_the_widget_key_is_not_the_preference_key() -> None:
    """The specific collision that caused the crash, pinned as a fact rather than a convention."""
    from frontend import theme

    assert theme._TOGGLE_KEY != f"lab.{theme._PREF_KEY}"
    assert theme._TOGGLE_KEY == WIDGET_KEY


def test_toggling_switches_the_theme_and_survives_a_rerun() -> None:
    """Flipping it was the operation that raised, so flip it -- both ways."""
    app = AppTest.from_file(str(FRONTEND / "app.py"), default_timeout=_TIMEOUT_S)
    app.run()

    app.sidebar.toggle[0].set_value(False).run()
    assert not app.exception, [e.message for e in app.exception]
    assert app.session_state[PREF_KEY] == "light"
    assert app.sidebar.toggle[0].value is False

    app.sidebar.toggle[0].set_value(True).run()
    assert not app.exception, [e.message for e in app.exception]
    assert app.session_state[PREF_KEY] == "dark"
    assert app.sidebar.toggle[0].value is True
