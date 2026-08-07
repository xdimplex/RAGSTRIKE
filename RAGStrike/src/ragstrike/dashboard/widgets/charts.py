"""Charts: severity distribution and risk trend.

WHY THE DATA SHAPING IS SEPARATE FROM THE DRAWING
    ``severity_frame`` and ``trend_frame`` are pure and return lists of dictionaries. That is what
    the tests assert on. The ``render_*`` functions do nothing but hand those rows to Altair and
    Streamlit, so a charting-library change cannot silently alter what the numbers say.

WHY THE COLOURS ARE PASSED IN
    Altair would happily pick its own categorical palette, and then CRITICAL would be whatever hue
    Vega assigned it -- different from the badge next to it. The severity scale is pinned to the
    theme so one severity is one colour everywhere in the product.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ragstrike.dashboard.services.filters import SEVERITY_ORDER
from ragstrike.dashboard.services.models import parse_timestamp
from ragstrike.dashboard.theme.palette import Palette, severity_colour

#: A trend line needs two points; one point is a dot that implies a direction it does not have.
MIN_TREND_POINTS = 2


def severity_frame(counts: Mapping[str, int]) -> list[dict[str, Any]]:
    """Severity counts as chart rows, worst first, including the zeroes.

    Zeroes are kept on purpose: a distribution that silently omits ``CRITICAL: 0`` looks identical to
    one that was never measured, and the difference is the whole point of the chart.
    """
    normalised = {str(key).upper(): int(value) for key, value in counts.items()}
    return [{"severity": name, "count": normalised.get(name, 0)} for name in SEVERITY_ORDER]


def trend_frame(points: Sequence[tuple[str, float]]) -> list[dict[str, Any]]:
    """(timestamp, risk) pairs as chart rows, dropping unparseable timestamps.

    Dropped rather than plotted at epoch zero: one bad timestamp at 1970 compresses the entire
    visible range into a pixel, which loses the ten points that were fine.
    """
    rows: list[dict[str, Any]] = []
    for raw, score in points:
        stamp = parse_timestamp(raw)
        if stamp is None:
            continue
        rows.append({"when": stamp.isoformat(), "risk": float(score)})
    return rows


def severity_scale(palette: Palette) -> tuple[list[str], list[str]]:
    """(domain, range) for a pinned Altair colour scale."""
    return list(SEVERITY_ORDER), [severity_colour(palette, name) for name in SEVERITY_ORDER]


def render_severity_chart(palette: Palette, counts: Mapping[str, int]) -> None:
    """Draw the severity distribution as a horizontal bar chart."""
    import altair as alt
    import pandas as pd
    import streamlit as st

    rows = severity_frame(counts)
    if not any(row["count"] for row in rows):
        return

    domain, colours = severity_scale(palette)
    chart = (
        alt.Chart(pd.DataFrame(rows))
        .mark_bar(cornerRadiusEnd=3, height=18)
        .encode(
            x=alt.X("count:Q", title=None, axis=alt.Axis(grid=False, tickMinStep=1)),
            y=alt.Y("severity:N", title=None, sort=domain),
            color=alt.Color(
                "severity:N",
                scale=alt.Scale(domain=domain, range=colours),
                legend=None,
            ),
            tooltip=["severity:N", "count:Q"],
        )
        .properties(height=150)
        .configure_view(strokeWidth=0)
        .configure_axis(labelColor=palette.text_muted, domainColor=palette.border)
    )
    st.altair_chart(chart, width="stretch")


def render_trend_chart(palette: Palette, points: Sequence[tuple[str, float]]) -> None:
    """Draw the per-target risk trend.

    The y axis is pinned to 0-100 rather than fitted to the data. An auto-fitted axis makes a drift
    from 91 to 93 look like a cliff, which is exactly the misreading a security dashboard should not
    manufacture.
    """
    import altair as alt
    import pandas as pd
    import streamlit as st

    rows = trend_frame(points)
    if len(rows) < MIN_TREND_POINTS:
        return

    frame = pd.DataFrame(rows)
    base = alt.Chart(frame).encode(
        x=alt.X("when:T", title=None, axis=alt.Axis(grid=False)),
        y=alt.Y("risk:Q", title="Risk", scale=alt.Scale(domain=[0, 100])),
        tooltip=["when:T", "risk:Q"],
    )
    chart = (
        (
            base.mark_area(opacity=0.14, color=palette.accent)
            + base.mark_line(color=palette.accent, point=True)
        )
        .properties(height=170)
        .configure_view(strokeWidth=0)
        .configure_axis(labelColor=palette.text_muted, domainColor=palette.border)
    )
    st.altair_chart(chart, width="stretch")
