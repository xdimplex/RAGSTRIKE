"""The pinned Streamlit base theme must match the DARK palette, and light mode must be able to win.

WHY THIS FILE EXISTS
    Two defects, both reported as "the dashboard is half dark and half light".

    **The base theme is pinned.** ``.streamlit/config.toml`` sets ``base = "dark"`` because
    Streamlit paints its own chrome before the app's stylesheet arrives, and an unpinned base
    flashes white on every load. That pin is static -- it cannot know which theme the current
    session chose -- so in LIGHT mode the compiled base theme is still dark, and its rules land
    after ours in the cascade. Content repainted light, native chrome stayed dark.

    The fix is `!important` on the container surfaces, which is checked here so nobody removes it
    as "unnecessary" -- it is the only thing making the stylesheet authoritative in both directions.

    **The pinned values had drifted.** All four differed from the palette they are documented to
    mirror (``#0b0f14`` vs ``#0d1117``, and so on). The symptom is a flash of the wrong colour at
    load, which is easy to miss by eye and exactly what a test should carry instead.
"""

from __future__ import annotations

from pathlib import Path
import re
import tomllib

import pytest

from ragstrike.dashboard.theme.palette import DARK, LIGHT
from ragstrike.dashboard.theme.styles import stylesheet

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = REPO_ROOT / ".streamlit" / "config.toml"


@pytest.fixture(scope="module")
def theme_config() -> dict[str, str]:
    return tomllib.loads(CONFIG.read_text())["theme"]


def test_the_pinned_base_is_dark(theme_config: dict[str, str]) -> None:
    """Unpinned, Streamlit defaults to light and every dark session flashes white on load."""
    assert theme_config["base"] == "dark"


@pytest.mark.parametrize(
    ("config_key", "palette_attr"),
    [
        ("backgroundColor", "background"),
        ("secondaryBackgroundColor", "surface"),
        ("textColor", "text"),
        ("primaryColor", "accent"),
    ],
)
def test_pinned_values_match_the_dark_palette(
    theme_config: dict[str, str], config_key: str, palette_attr: str
) -> None:
    expected = getattr(DARK, palette_attr)
    actual = theme_config[config_key]
    assert actual.lower() == expected.lower(), (
        f"{config_key}={actual} but palette.DARK.{palette_attr}={expected} -- "
        f"they must stay in sync or the first paint flashes the wrong colour"
    )


#: Selectors whose background must be forced. Each one was visibly wrong in light mode.
FORCED_SURFACES = ('.stApp', '[data-testid="stSidebar"]')


@pytest.mark.parametrize("palette", [DARK, LIGHT], ids=lambda p: p.name)
@pytest.mark.parametrize("selector", FORCED_SURFACES)
def test_container_surfaces_are_forced(palette, selector: str) -> None:
    """Without `!important` the pinned dark base wins in light mode -- the half-and-half console."""
    css = stylesheet(palette)
    block = _rule_containing(css, selector, declaring="background")
    assert block is not None, f"no rule sets a background for {selector}"
    assert _declaration_is_forced(block, "background"), (
        f"{selector} does not force its background; the pinned dark base theme will override it "
        f"whenever the operator selects light"
    )


def test_the_active_nav_item_still_wins() -> None:
    """The forced base rule must not flatten the selected item.

    `background: transparent !important` on the base button rule outranks any plain declaration
    regardless of order, so the active-item and hover rules need `!important` too or the rail loses
    every affordance it has.
    """
    css = stylesheet(DARK)
    active = _rule_containing(css, '.stButton > button[kind="primary"]', declaring="background")
    hover = _rule_containing(css, ".stButton > button:hover", declaring="background")

    assert active and _declaration_is_forced(active, "background"), "active nav item flattened"
    assert hover and _declaration_is_forced(hover, "background"), "hover state flattened"


def test_both_palettes_produce_their_own_background() -> None:
    """A sanity check that the stylesheet is actually palette-driven rather than hardcoded."""
    assert DARK.background in stylesheet(DARK)
    assert LIGHT.background in stylesheet(LIGHT)
    assert LIGHT.background not in stylesheet(DARK)


def _declaration_is_forced(block: str, prop: str) -> bool:
    """Is *prop* specifically marked ``!important`` in this block?

    Asking whether the block contains ``!important`` anywhere is not the same question, and the
    difference is not academic: the ``.stApp`` rule also forces ``color``, so a looser check stayed
    green after the ``background`` guard was deliberately stripped out. A test that survives the
    removal of the thing it exists to protect is worse than no test.
    """
    match = re.search(rf"(?:^|[;{{\s]){re.escape(prop)}\s*:([^;}}]*)", block)
    return bool(match) and "!important" in match.group(1)


def _rule_containing(css: str, selector: str, declaring: str | None = None) -> str | None:
    """Declaration block of the first rule matching *selector* and, if given, setting *declaring*.

    The ``declaring`` filter is not optional decoration. ``.stApp`` appears first in a rule that
    only defines custom properties (``--background-color: …``), so a naive "first match" search
    finds a block with no ``background`` in it at all and reports a missing ``!important`` that was
    never meant to be there.
    """
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        selectors, body = match.group(1), match.group(2)
        if selector not in selectors:
            continue
        if declaring and not re.search(rf"(^|[;\s]){re.escape(declaring)}\s*:", body):
            continue
        return body
    return None
