"""The console chrome: fixed tables, the status rail, and the density decisions behind them.

WHY THESE EXIST
    The dashboard was restyled from a comfortable reading layout into a dense assessment console.
    Three properties of that change are load-bearing rather than cosmetic, and each has already been
    a defect once:

    * **A table must not be draggable.** ``st.dataframe`` renders a resizable grid that ignores the
      theme; a plain ``<table>`` with ``table-layout: fixed`` is what makes column widths a design
      decision instead of whatever the last user dragged.
    * **A cell must escape its contents.** A findings table carries the TARGET's own response, which
      is to say attacker-influenced text. An unescaped cell would make the report an XSS vector
      against the tool that produced it.
    * **The stylesheet must cover Streamlit's own chrome.** Redefining Streamlit's theme variables
      is what makes a theme toggle repaint native widgets; without it the page is half dark.
"""

from __future__ import annotations

import sys
import types

import pytest

from ragstrike.dashboard.theme import stylesheet
from ragstrike.dashboard.theme.palette import palette_for
from ragstrike.dashboard.widgets.tables import _cell, _column_class, _slug

# -- table cells -----------------------------------------------------------------------------------


def test_a_cell_escapes_its_contents() -> None:
    """A findings table carries text the target produced. It is not trusted."""
    rendered = _cell("Finding", "<script>alert(1)</script>")

    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_a_status_cell_becomes_a_pill() -> None:
    rendered = _cell("Status", "FAIL")

    assert 'class="rs-t-pill rs-t-pill--fail"' in rendered


def test_an_unknown_status_still_carries_the_base_pill_class() -> None:
    """The base class supplies a neutral grey, so a status the UI has never seen renders as
    *unknown* rather than unstyled -- and never accidentally as severe."""
    rendered = _cell("Status", "Some-New-State")

    assert "rs-t-pill " in rendered


def test_booleans_read_as_words_rather_than_python_literals() -> None:
    assert ">yes<" in _cell("Enabled", True)
    assert ">no<" in _cell("Enabled", False)


@pytest.mark.parametrize("value", ["", "--"])
def test_placeholder_values_are_not_dressed_up_as_pills(value: str) -> None:
    """A missing value is missing. Rendering it as a coloured badge asserts a status nobody set."""
    assert "rs-t-pill" not in _cell("Status", value)


def test_numeric_columns_are_right_aligned_and_tabular() -> None:
    """A column of numbers aligned left is unreadable."""
    classes = _column_class("Risk")

    assert "rs-t-num" in classes
    assert "rs-t-mono" in classes


def test_slugs_survive_awkward_values() -> None:
    assert _slug("Not run") == "not-run"
    assert _slug("") == "none"


# -- the status rail -------------------------------------------------------------------------------


@pytest.fixture
def captured_markdown(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Exercise the rail without a Streamlit server by capturing what it writes."""
    written: list[str] = []
    fake = types.ModuleType("streamlit")
    fake.markdown = lambda body, **_: written.append(body)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "streamlit", fake)
    return written


def test_an_empty_rail_renders_nothing(captured_markdown: list[str]) -> None:
    """An empty strip of chrome is worse than no strip: it reads as data that failed to load."""
    from ragstrike.dashboard.layouts.page_layout import rail

    rail([])

    assert captured_markdown == []


def test_the_rail_escapes_its_values(captured_markdown: list[str]) -> None:
    from ragstrike.dashboard.layouts.page_layout import rail

    rail([("Target", "<b>x</b>")])

    assert "&lt;b&gt;" in captured_markdown[-1]
    assert "<b>x</b>" not in captured_markdown[-1]


def test_the_rail_pairs_every_label_with_a_value(captured_markdown: list[str]) -> None:
    from ragstrike.dashboard.layouts.page_layout import rail

    rail([("Scans", "3"), ("Worst risk", "8.4")])

    body = captured_markdown[-1]
    assert body.count("rs-rail__label") == 2
    assert body.count("rs-rail__value") == 2


# -- the stylesheet --------------------------------------------------------------------------------


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_the_stylesheet_covers_streamlit_native_chrome(theme: str) -> None:
    """Redefining Streamlit's own variables is what makes the toggle repaint native widgets.

    Without it the custom components follow the theme and every input, select, tab, and code block
    keeps Streamlit's defaults -- the "half dark, half light" page.
    """
    css = stylesheet(palette_for(theme))

    for expected in ("--background-color", "--text-color", "stAppViewContainer", "stSidebar"):
        assert expected in css, f"{theme} stylesheet does not cover {expected}"


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_the_console_chrome_is_present(theme: str) -> None:
    css = stylesheet(palette_for(theme))

    for expected in (".rs-rail", ".rs-section", ".rs-table", ".rs-card"):
        assert expected in css, f"{theme} stylesheet is missing {expected}"


def test_the_two_palettes_actually_differ() -> None:
    """A toggle that produces the same stylesheet twice is a toggle that does nothing."""
    assert stylesheet(palette_for("dark")) != stylesheet(palette_for("light"))
