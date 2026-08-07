"""Progress bars, including the one that watches a live scan."""

from __future__ import annotations

from ragstrike.dashboard.components.html import escape, join, style, tag
from ragstrike.dashboard.services.models import ScanProgress
from ragstrike.dashboard.theme.palette import Palette, outcome_colour

SECONDS_PER_MINUTE = 60
MINUTES_PER_HOUR = 60


def format_duration(seconds: float) -> str:
    """Human duration. Mirrors the reporting engine's formatter in behaviour, not in code.

    Not imported from ``ragstrike.reporters.models.formatting``: that import would pull the reporting
    engine -- and transitively the analyzer and the domain model -- into the dashboard, breaking
    contract 3. Twelve lines of duplication is the honest price of the boundary.
    """
    total = max(0, round(seconds))
    if total < SECONDS_PER_MINUTE:
        return f"{total}s"
    minutes, secs = divmod(total, SECONDS_PER_MINUTE)
    if minutes < MINUTES_PER_HOUR:
        return f"{minutes}m {secs:02d}s"
    hours, minutes = divmod(minutes, MINUTES_PER_HOUR)
    return f"{hours}h {minutes:02d}m"


def progress_bar(
    fraction: float,
    colour: str,
    *,
    left: str = "",
    right: str = "",
) -> str:
    """A labelled bar. ``fraction`` is clamped, so a backend reporting 7/5 does not overflow it."""
    pct = min(1.0, max(0.0, fraction))
    fill = tag(
        "div",
        "",
        class_="rs-bar__fill",
        style=style({"width": f"{pct * 100:.1f}%", "background": colour}),
    )
    bar = tag("div", fill, class_="rs-bar")
    meta = (
        tag(
            "div",
            tag("span", escape(left)) + tag("span", escape(right)),
            class_="rs-bar__meta",
        )
        if left or right
        else ""
    )
    return bar + meta


def scan_progress(palette: Palette, progress: ScanProgress) -> str:
    """The live scan panel: stage, plugin, counts, and estimated time.

    "Estimated" is in the label on purpose. A countdown that looks authoritative and is wrong by a
    factor of three is worse than one the operator knows to treat as a guess.
    """
    colour = outcome_colour(palette, progress.state)
    bar = progress_bar(
        progress.percent,
        colour,
        # "packs", not "cases". The counter has always been one tick per attack pack, and calling
        # them cases invited the reading that it was payloads -- which made "2 / 2" look like a
        # scan that had barely started when it was a complete smoke run.
        left=f"{progress.completed} / {progress.total} packs" if progress.total else progress.state,
        right=f"{progress.percent * 100:.0f}%",
    )
    facts = [
        ("State", progress.state.upper()),
        ("Plugin", progress.current_plugin),
        ("Stage", progress.current_stage),
        ("Est. remaining", format_duration(progress.eta_s) if progress.eta_s else ""),
        ("Findings so far", str(progress.findings_so_far) if progress.findings_so_far else ""),
    ]
    detail = join(
        tag(
            "div",
            tag("div", escape(label), class_="rs-label")
            + tag("div", escape(value), class_="rs-kv__v"),
            class_="rs-stack",
            style=style({"min-width": "128px"}),
        )
        for label, value in facts
        if value
    )
    return tag(
        "div",
        bar + tag("div", detail, class_="rs-row", style=style({"margin-top": "14px"})),
        class_="rs-card",
    )


def severity_bars(palette: Palette, counts: dict[str, int]) -> str:
    """A stacked set of per-severity bars, worst first.

    Bars rather than a pie: comparing angles is harder than comparing lengths, and the question an
    operator asks here is "how many criticals", not "what proportion".
    """
    order = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
    present = {key.upper(): int(value) for key, value in counts.items()}
    largest = max(present.values(), default=0)
    if largest <= 0:
        return ""
    rows = []
    for name in order:
        count = present.get(name, 0)
        colour = str(getattr(palette, {"INFO": "informational"}.get(name, name.lower())))
        rows.append(
            tag(
                "div",
                tag("div", escape(name), class_="rs-label")
                + progress_bar(count / largest, colour, right=str(count)),
                class_="rs-stack",
                style=style({"margin-bottom": "8px"}),
            )
        )
    return join(rows)
