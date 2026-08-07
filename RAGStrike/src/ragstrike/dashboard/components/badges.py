"""Badges: severity, risk, outcome, grade, and the generic pill they share.

DESIGN NOTE
    Colour is carried on the *text and border*, not as a filled background. Twelve filled HIGH badges
    in a table turn the page into a warning light and stop distinguishing anything; outlined badges
    stay legible at density, which is what a findings table needs.
"""

from __future__ import annotations

from ragstrike.dashboard.components.html import escape, style, tag
from ragstrike.dashboard.theme.palette import (
    Palette,
    grade_colour,
    outcome_colour,
    severity_colour,
)

#: Risk-score bands (SDD 17.3). Read as "score is at least this", checked worst first.
RISK_BANDS: tuple[tuple[float, str, str], ...] = (
    (90.0, "CRITICAL", "critical"),
    (70.0, "HIGH", "high"),
    (40.0, "MEDIUM", "medium"),
    (10.0, "LOW", "low"),
    (0.0, "MINIMAL", "informational"),
)


def risk_band(score: float) -> tuple[str, str]:
    """(label, palette attribute) for a 0-100 risk score."""
    for threshold, label, attribute in RISK_BANDS:
        if score >= threshold:
            return label, attribute
    return "MINIMAL", "informational"


def badge(label: str, colour: str, *, dot: bool = True, title: str = "") -> str:
    """The generic pill every other badge is built from."""
    marker = tag("span", "", class_="rs-badge__dot") if dot else ""
    return tag(
        "span",
        marker + escape(label),
        class_="rs-badge",
        style=style({"color": colour}),
        title=title or None,
    )


def severity_badge(palette: Palette, severity: str) -> str:
    """A severity pill. Unknown severities render in the informational colour, never in red."""
    return badge(severity.upper() or "UNKNOWN", severity_colour(palette, severity))


def outcome_badge(palette: Palette, outcome: str) -> str:
    """A plugin outcome or scan state.

    INCONCLUSIVE is deliberately warning-coloured rather than grey: "we could not tell" is a result
    that needs attention, and greying it out is how it gets read as "fine".
    """
    return badge(outcome.upper() or "UNKNOWN", outcome_colour(palette, outcome))


def risk_badge(palette: Palette, score: float) -> str:
    """A risk score with its band, e.g. ``94.0 CRITICAL``."""
    label, attribute = risk_band(score)
    colour = str(getattr(palette, attribute))
    return badge(f"{score:.1f} {label}", colour, title=f"Risk score {score:.1f} of 100")


def grade_badge(palette: Palette, grade: str) -> str:
    """A small posture-grade pill, for tables. See :func:`grade_hero` for the large one."""
    if not grade:
        return badge("UNGRADED", palette.neutral, dot=False)
    return badge(grade.upper(), grade_colour(palette, grade), dot=False)


def grade_hero(palette: Palette, grade: str, *, coverage: float = 1.0) -> str:
    """The large grade panel.

    Always rendered with its coverage qualifier (ADR-020): a grade computed from half the intended
    cases is not the same claim as one computed from all of them, and showing the letter alone
    invites it to be quoted as though it were.
    """
    letter = (grade or "?").upper()[:1]
    colour = grade_colour(palette, letter) if grade else palette.neutral
    block = tag("div", escape(letter), class_="rs-grade", style=style({"color": colour}))
    qualifier = tag(
        "div",
        escape(f"coverage {coverage * 100:.0f}%"),
        class_="rs-metric__hint",
    )
    return tag("div", block + qualifier, class_="rs-stack")
