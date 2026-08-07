"""The log viewer.

SAFETY
    Log lines contain payload text and target responses -- which is to say, they contain whatever an
    injection payload said. Every field is escaped. A log viewer that renders its input is a stored
    XSS sink whose input is a corpus of attack strings.
"""

from __future__ import annotations

from collections.abc import Sequence

from ragstrike.dashboard.components.html import escape, join, style, tag
from ragstrike.dashboard.services.models import LogLine
from ragstrike.dashboard.theme.palette import Palette

#: Level to palette attribute. Anything unrecognised renders muted rather than alarming.
LEVEL_COLOURS: dict[str, str] = {
    "DEBUG": "text_faint",
    "INFO": "text_muted",
    "WARNING": "warn",
    "WARN": "warn",
    "ERROR": "danger",
    "CRITICAL": "critical",
}

#: Level ranks for filtering. A level the dashboard does not know about is always shown -- hiding an
#: unrecognised line is how a new ``FATAL`` level would go unnoticed.
LEVEL_RANK: dict[str, int] = {
    "DEBUG": 10,
    "INFO": 20,
    "WARNING": 30,
    "WARN": 30,
    "ERROR": 40,
    "CRITICAL": 50,
}


def visible_lines(lines: Sequence[LogLine], minimum_level: str) -> list[LogLine]:
    """Filter by level, keeping unknown levels."""
    floor = LEVEL_RANK.get(minimum_level.strip().upper(), 0)
    return [line for line in lines if LEVEL_RANK.get(line.level.strip().upper(), floor) >= floor]


def log_viewer(
    palette: Palette,
    lines: Sequence[LogLine],
    *,
    minimum_level: str = "DEBUG",
    limit: int = 300,
) -> str:
    """Render log lines newest-last, capped.

    Capped because a scan can produce tens of thousands of lines and a browser asked to lay them all
    out stops responding -- at which point the operator cannot read any of them.
    """
    selected = visible_lines(lines, minimum_level)[-limit:]
    if not selected:
        return tag(
            "div",
            escape("No log output yet."),
            class_="rs-log",
            style=style({"color": palette.text_faint}),
        )
    rendered = join(
        tag(
            "div",
            tag(
                "span",
                escape(line.timestamp[-8:] if line.timestamp else "--:--:--"),
                class_="rs-log__ts",
            )
            + tag(
                "span",
                escape(line.level),
                class_="rs-log__lvl",
                style=style(
                    {
                        "color": str(
                            getattr(palette, LEVEL_COLOURS.get(line.level.upper(), "text_muted"))
                        )
                    }
                ),
            )
            + tag("span", escape(line.message)),
            class_="rs-log__line",
        )
        for line in selected
    )
    return tag("div", rendered, class_="rs-log")
