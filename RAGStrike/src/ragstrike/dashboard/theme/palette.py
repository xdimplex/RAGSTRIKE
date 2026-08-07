"""Named colours, and the semantic lookups that map domain vocabulary onto them.

THE RULE
    Severity and outcome colours are **not** decorative. An operator scanning a findings table reads
    colour before text, so a MEDIUM that renders in the HIGH colour is a misreport. The mappings
    below are therefore total -- every enum member the engine can emit has an entry -- and the
    lookups fall back to a deliberately unremarkable grey rather than raising, because a dashboard
    that crashes on an unknown severity tells the operator nothing while hiding everything else.

WHY GREY IS THE FALLBACK AND NOT RED
    An unrecognised value is *unknown*, not *severe*. Painting it red would manufacture alarm from a
    version mismatch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class Palette:
    """One complete colour scheme.

    Slots and frozen: a palette is a value. Two palettes with the same colours are the same palette,
    and nothing can tint one in place halfway through a render.
    """

    name: str
    #: True when the scheme is dark; drives Streamlit's own ``base`` setting and chart defaults.
    dark: bool

    # -- surfaces ---------------------------------------------------------------------------------
    background: str
    surface: str
    surface_raised: str
    border: str
    border_strong: str

    # -- text -------------------------------------------------------------------------------------
    text: str
    text_muted: str
    text_faint: str

    # -- brand ------------------------------------------------------------------------------------
    accent: str
    accent_soft: str

    # -- state ------------------------------------------------------------------------------------
    ok: str
    warn: str
    danger: str
    info: str
    neutral: str

    # -- severity, in the engine's own vocabulary -------------------------------------------------
    critical: str
    high: str
    medium: str
    low: str
    informational: str


# A cool slate console, not a blue-black one.
#
# The previous surfaces were near-navy (#0b0f14 / #121821), which reads as a consumer dark mode.
# A security tool wants neutral slate with clearly SEPARATED elevation levels: the operator needs
# to see panel boundaries at a glance while scanning, and near-identical greys make a dense grid
# look like an undifferentiated wall. Each step below is a visible level apart, and the borders
# are strong enough to draw panel chrome without a shadow.
DARK: Final = Palette(
    name="dark",
    dark=True,
    background="#0d1117",
    surface="#151b23",
    surface_raised="#1c242e",
    border="#2b3541",
    border_strong="#3d4a59",
    text="#e8edf2",
    text_muted="#a3b1c0",
    text_faint="#6e7d8c",
    accent="#4c9aff",
    accent_soft="rgba(76, 154, 255, 0.13)",
    ok="#31c48d",
    warn="#f7b955",
    danger="#f2555a",
    info="#5aa9e6",
    neutral="#7d8fa1",
    critical="#ff4d4f",
    high="#ff7a45",
    medium="#f7b955",
    low="#4dabf7",
    informational="#8899a8",
)

LIGHT: Final = Palette(
    name="light",
    dark=False,
    background="#f5f7fa",
    surface="#ffffff",
    surface_raised="#fbfcfe",
    border="#dde3ea",
    border_strong="#c2cdd8",
    text="#111820",
    text_muted="#4a5b6b",
    text_faint="#7c8b99",
    accent="#0b6bcb",
    accent_soft="rgba(11, 107, 203, 0.10)",
    ok="#0f8a5f",
    warn="#b26a00",
    danger="#c62828",
    info="#0b6bcb",
    neutral="#5f6f7e",
    critical="#c62828",
    high="#d1541f",
    medium="#b26a00",
    low="#1565c0",
    informational="#5f6f7e",
)

#: Registered themes. Adding one is an entry here plus a :class:`Palette` -- the brief's "Future
#: Custom Themes" needs no code change anywhere else.
PALETTES: Final[dict[str, Palette]] = {p.name: p for p in (DARK, LIGHT)}


def palette_for(name: str) -> Palette:
    """Look up a palette, falling back to dark.

    Falls back rather than raising: an unknown theme name in a config file should not be the reason
    an operator cannot open the tool.
    """
    return PALETTES.get(name.strip().lower(), DARK)


# -------------------------------------------------------------------------------------------------
# Semantic lookups.
#
# These take the *engine's* string vocabulary -- Severity and PluginOutcome names -- without
# importing the enums, because importing them would import ragstrike.models and break contract 3.
# The strings are the wire format the API already returns, so this is not a private coupling; it is
# the same contract every other API client would code against.
# -------------------------------------------------------------------------------------------------

_SEVERITY: Final[dict[str, str]] = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "info": "informational",
    "informational": "informational",
}

_OUTCOME: Final[dict[str, str]] = {
    "pass": "ok",
    "fail": "danger",
    "inconclusive": "warn",
    "error": "critical",
    "skipped": "neutral",
    # Scan states, which share the badge component with plugin outcomes.
    "running": "info",
    "queued": "neutral",
    "completed": "ok",
    "failed": "danger",
    "cancelled": "neutral",
}

#: Posture grades (SDD 17.5). A and B are healthy, C and D are warnings, E and F are failures.
_GRADE: Final[dict[str, str]] = {
    "a": "ok",
    "b": "ok",
    "c": "warn",
    "d": "warn",
    "e": "danger",
    "f": "critical",
}


def _resolve(palette: Palette, attribute: str) -> str:
    return str(getattr(palette, attribute))


def severity_colour(palette: Palette, severity: str) -> str:
    """Colour for a severity name. Unknown names render as informational, never as critical."""
    return _resolve(palette, _SEVERITY.get(severity.strip().lower(), "informational"))


def outcome_colour(palette: Palette, outcome: str) -> str:
    """Colour for a plugin outcome or a scan state."""
    return _resolve(palette, _OUTCOME.get(outcome.strip().lower(), "neutral"))


def grade_colour(palette: Palette, grade: str) -> str:
    """Colour for a posture grade A-F."""
    return _resolve(palette, _GRADE.get(grade.strip().lower()[:1], "neutral"))
