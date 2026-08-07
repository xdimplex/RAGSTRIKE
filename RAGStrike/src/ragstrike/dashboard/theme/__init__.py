"""The theme system: palettes, design tokens, and the stylesheet built from them.

Every colour the dashboard draws comes from a :class:`~ragstrike.dashboard.theme.palette.Palette`.
Nothing hardcodes a hex value outside this package -- which is what makes "add a custom theme" a
data change rather than a search-and-replace across forty files.
"""

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
from ragstrike.dashboard.theme.styles import stylesheet
from ragstrike.dashboard.theme.tokens import TOKENS, Tokens

__all__ = [
    "DARK",
    "LIGHT",
    "PALETTES",
    "TOKENS",
    "Palette",
    "Tokens",
    "grade_colour",
    "outcome_colour",
    "palette_for",
    "severity_colour",
    "stylesheet",
]
