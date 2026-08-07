"""The activity timeline, used on Home and on a scan's detail view."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ragstrike.dashboard.components.html import escape, join, style, tag
from ragstrike.dashboard.theme.palette import Palette, outcome_colour


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    """One dot on the timeline."""

    title: str
    timestamp: str = ""
    detail: str = ""
    #: A plugin outcome or scan state; drives the dot colour through the shared lookup so a FAIL on
    #: the timeline is the same red as a FAIL in the findings table.
    kind: str = "info"


def timeline(palette: Palette, events: Sequence[TimelineEvent], *, limit: int = 12) -> str:
    """Render events newest-first."""
    if not events:
        return ""
    items = join(
        tag(
            "div",
            tag(
                "span",
                "",
                class_="rs-timeline__dot",
                style=style({"background": outcome_colour(palette, event.kind)}),
            )
            + tag("div", escape(event.title), class_="rs-timeline__title")
            + tag(
                "div",
                escape(" · ".join(part for part in (event.timestamp, event.detail) if part)),
                class_="rs-timeline__meta",
            ),
            class_="rs-timeline__item",
        )
        for event in events[:limit]
    )
    return tag("div", items, class_="rs-timeline")
