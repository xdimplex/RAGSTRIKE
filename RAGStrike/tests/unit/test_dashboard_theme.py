"""Theme tests.

THE CLAIM UNDER TEST: **adding a theme is a data change, not a code change.**

Every colour the dashboard draws comes from a :class:`Palette`. If a component hardcoded a hex
value, dark mode would look right and light mode would be unreadable -- and no test that only
renders the dark theme would notice. So these tests check both palettes are complete, that the
stylesheet is generated from whichever one it is given, and that no module outside ``theme/``
contains a colour literal.
"""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path
import re

import pytest

from ragstrike.dashboard.theme.palette import (
    DARK,
    LIGHT,
    PALETTES,
    Palette,
    grade_colour,
    outcome_colour,
    palette_for,
    severity_colour,
)
from ragstrike.dashboard.theme.styles import css_variables, stylesheet
from ragstrike.dashboard.theme.tokens import TOKENS, Tokens

DASHBOARD = Path("src/ragstrike/dashboard")

#: A six- or three-digit hex colour. Deliberately does not match ``rgba(...)``, which the palette
#: itself uses for the soft accent.
HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b")


# -- palettes --------------------------------------------------------------------------------------


def test_both_shipped_themes_are_registered() -> None:
    assert set(PALETTES) == {"dark", "light"}


def test_a_palette_defines_every_colour_slot() -> None:
    """A palette with a missing slot would raise on whichever component used it first -- possibly
    the one an operator only reaches when something has already gone wrong."""
    for palette in (DARK, LIGHT):
        for spec in fields(Palette):
            value = getattr(palette, spec.name)
            assert value != "", f"{palette.name}.{spec.name} is empty"


def test_the_two_palettes_define_exactly_the_same_slots() -> None:
    """Any divergence means a component works in one theme and breaks in the other."""
    assert {f.name for f in fields(DARK)} == {f.name for f in fields(LIGHT)}


def test_dark_and_light_actually_differ() -> None:
    """A "light" theme that is a copy of dark passes every other test in this file."""
    assert DARK.background != LIGHT.background
    assert DARK.text != LIGHT.text
    assert DARK.dark and not LIGHT.dark


def test_severities_are_distinguishable_within_a_palette() -> None:
    """Two severities sharing a colour is a misreport an operator reads before the text."""
    for palette in (DARK, LIGHT):
        colours = [
            severity_colour(palette, name) for name in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
        ]
        assert len(set(colours)) == len(colours), f"{palette.name} reuses a severity colour"


def test_an_unknown_theme_name_falls_back_rather_than_raising() -> None:
    """A stale theme name in a config file should not be why an operator cannot open the tool."""
    assert palette_for("solarized-mauve") is DARK
    assert palette_for("") is DARK


def test_theme_lookup_ignores_case_and_whitespace() -> None:
    assert palette_for("  LIGHT ") is LIGHT


# -- semantic lookups ------------------------------------------------------------------------------


@pytest.mark.parametrize("severity", ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO", "INFORMATIONAL"])
def test_every_severity_the_engine_emits_has_a_colour(severity: str) -> None:
    assert severity_colour(DARK, severity)


@pytest.mark.parametrize("outcome", ["PASS", "FAIL", "INCONCLUSIVE", "ERROR", "SKIPPED"])
def test_every_plugin_outcome_has_a_colour(outcome: str) -> None:
    """The five ``PluginOutcome`` members, INCONCLUSIVE included -- it was added in Phase 6 and a
    lookup that predates it would ``KeyError`` mid-scan."""
    assert outcome_colour(DARK, outcome)


@pytest.mark.parametrize("state", ["queued", "running", "completed", "failed", "cancelled"])
def test_every_scan_state_has_a_colour(state: str) -> None:
    assert outcome_colour(DARK, state)


@pytest.mark.parametrize("grade", list("ABCDEF"))
def test_every_posture_grade_has_a_colour(grade: str) -> None:
    assert grade_colour(DARK, grade)


def test_grades_are_read_from_the_first_letter() -> None:
    """The engine may render a grade as "F (81)"."""
    assert grade_colour(DARK, "F (81)") == grade_colour(DARK, "F")


def test_unknown_values_resolve_to_neutral_rather_than_alarm() -> None:
    assert outcome_colour(DARK, "quantum") == DARK.neutral
    assert grade_colour(DARK, "?") == DARK.neutral


# -- tokens ----------------------------------------------------------------------------------------


def test_tokens_are_palette_independent() -> None:
    """Dark and light differ in colour, not in rhythm. One token set is the point."""
    assert isinstance(TOKENS, Tokens)
    assert TOKENS.space_md.endswith("px")


def test_the_monospace_stack_has_a_generic_fallback() -> None:
    """Payloads and canaries are the primary evidence; proportional fallback makes whitespace
    differences invisible."""
    assert TOKENS.font_mono.rstrip().endswith("monospace")


# -- the generated stylesheet ----------------------------------------------------------------------


def test_the_variable_block_carries_every_palette_colour() -> None:
    block = css_variables(DARK)

    for name in ("background", "surface", "critical", "high", "medium", "low"):
        assert getattr(DARK, name) in block, f"--rs-{name} missing"


def test_switching_palette_switches_the_stylesheet() -> None:
    """The whole theme mechanism, in one assertion."""
    assert DARK.background in stylesheet(DARK)
    assert DARK.background not in stylesheet(LIGHT)
    assert LIGHT.background in stylesheet(LIGHT)


def test_the_stylesheet_is_a_complete_style_element() -> None:
    css = stylesheet(DARK)

    assert css.startswith("<style>")
    assert css.rstrip().endswith("</style>")


def test_the_stylesheet_defines_the_classes_the_components_emit() -> None:
    """A component emitting a class the stylesheet never defines renders unstyled, which looks like
    a broken page rather than a missing rule."""
    css = stylesheet(DARK)

    for name in (
        "rs-card",
        "rs-badge",
        "rs-metric",
        "rs-bar",
        "rs-log",
        "rs-timeline",
        "rs-empty",
        "rs-toast",
        "rs-overlay",
        "rs-kv",
        "rs-banner",
        "rs-header",
        "rs-grade",
        "rs-label",
    ):
        assert f".{name}" in css, f"{name} is emitted but never styled"


def test_the_stylesheet_carries_responsive_rules() -> None:
    """ "Modern, responsive": the metric strip has to degrade on a narrow window rather than shrink
    numbers until they are unreadable."""
    assert "@media" in stylesheet(DARK)


def test_tokens_reach_the_stylesheet() -> None:
    custom = Tokens(radius_md="99px")

    assert "99px" in stylesheet(DARK, custom)


# -- the structural claim --------------------------------------------------------------------------


def _colour_literals(path: Path) -> list[str]:
    """Hex literals outside comments and docstrings.

    Crude on purpose: a false positive costs one ``# noqa``-style exemption in this test, and a
    false negative is a hardcoded colour that survives a theme change.
    """
    source = path.read_text(encoding="utf-8")
    return [
        match
        for line in source.splitlines()
        if not line.lstrip().startswith("#")
        for match in HEX_COLOUR.findall(line)
    ]


def test_no_colour_is_hardcoded_outside_the_theme_package() -> None:
    """This is what makes "Future Custom Themes" a data change.

    A component with a literal ``#f2555a`` would look correct today and be invisible under any
    palette someone adds tomorrow -- and would pass every rendering test, because the tests render
    the palette that happens to match.
    """
    offenders = {
        str(path.relative_to(DASHBOARD)): literals
        for path in DASHBOARD.rglob("*.py")
        if "theme" not in path.parts and (literals := _colour_literals(path))
    }

    assert offenders == {}


def test_the_theme_package_is_where_the_colours_live() -> None:
    """The counterpart to the test above: if this one ever finds nothing, the palettes have been
    emptied and the test above is passing vacuously."""
    assert _colour_literals(DASHBOARD / "theme" / "palette.py")
