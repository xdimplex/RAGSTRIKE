"""Cards: status, metric, plugin, target, and report.

Every builder here returns a string and touches no Streamlit API, which is why the component tests
can assert on the exact markup instead of on a screenshot.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ragstrike.dashboard.components.badges import (
    badge,
    grade_badge,
    outcome_badge,
    risk_badge,
    severity_badge,
)
from ragstrike.dashboard.components.html import escape, join, style, tag
from ragstrike.dashboard.services.models import PluginView, ReportView, TargetView
from ragstrike.dashboard.theme.palette import Palette, outcome_colour

#: Subsystem status to (glyph, palette attribute). ``unknown`` is grey and says so; it is not
#: optimistically drawn as healthy.
STATUS_MARKS: dict[str, tuple[str, str]] = {
    "ok": ("●", "ok"),
    "degraded": ("◐", "warn"),
    "down": ("○", "danger"),
    "disabled": ("◌", "neutral"),
    "unknown": ("?", "neutral"),
}


def key_values(pairs: Sequence[tuple[str, str]]) -> str:
    """The two-column definition list used inside most cards."""
    rows = join(
        tag("div", escape(key), class_="rs-kv__k") + tag("div", escape(value), class_="rs-kv__v")
        for key, value in pairs
        if value
    )
    return tag("div", rows, class_="rs-kv")


def status_card(palette: Palette, name: str, status: str, detail: str = "", meta: str = "") -> str:
    """One subsystem's health."""
    glyph, attribute = STATUS_MARKS.get(status.lower(), STATUS_MARKS["unknown"])
    colour = str(getattr(palette, attribute))
    head = tag(
        "div",
        tag("span", escape(glyph), style=style({"color": colour, "font-size": "1.05rem"}))
        + tag("span", escape(name), class_="rs-card__title"),
        class_="rs-row",
    )
    body = tag("div", escape(detail or status.upper()), class_="rs-card__body")
    foot = tag("div", escape(meta), class_="rs-card__foot") if meta else ""
    return tag(
        "div",
        head + body + foot,
        class_="rs-card rs-card--accented",
        style=style({"border-left-color": colour}),
    )


def metric_card(
    label: str,
    value: str,
    *,
    hint: str = "",
    delta: str = "",
    delta_colour: str = "",
) -> str:
    """A single number with its label.

    ``delta`` is rendered only when a colour is supplied, because "up" is good for coverage and bad
    for risk -- the caller knows which, and this component deliberately does not guess.
    """
    parts = [
        tag("div", escape(label), class_="rs-label"),
        tag("div", escape(value), class_="rs-metric__value"),
    ]
    if delta and delta_colour:
        parts.append(
            tag(
                "div",
                escape(delta),
                class_="rs-metric__delta",
                style=style({"color": delta_colour}),
            )
        )
    if hint:
        parts.append(tag("div", escape(hint), class_="rs-metric__hint"))
    return tag("div", tag("div", join(parts), class_="rs-metric"), class_="rs-card")


def plugin_card(palette: Palette, plugin: PluginView, *, framed: bool = True) -> str:
    """An installed plugin, active or refused.

    ``framed=False`` drops this card's own border and margin, for when the caller has already put it
    inside a bordered container. Two nested borders read as a bug, and the outer one is what keeps
    the plugin's action buttons visually attached to the plugin they act on.

    A refused plugin shows its reason in the body. Hiding the reason and showing only "rejected"
    would leave the operator with no way to tell a permission refusal from a version mismatch --
    two problems with completely different fixes.
    """
    state = badge(
        "ENABLED" if plugin.enabled else "DISABLED",
        palette.ok if plugin.enabled else palette.neutral,
        dot=False,
    )
    health = "" if plugin.healthy else badge("REFUSED", palette.danger)
    head = tag(
        "div",
        tag(
            "div",
            tag("span", escape(plugin.display_name), class_="rs-card__title")
            + tag("span", escape(plugin.version), class_="rs-metric__hint"),
            class_="rs-row",
        )
        + tag(
            "div", join([severity_badge(palette, plugin.severity), state, health]), class_="rs-row"
        ),
        class_="rs-row rs-row--split",
    )
    body = tag(
        "div",
        escape(plugin.rejection_reason or plugin.description),
        class_="rs-card__body",
        style=style({"color": palette.danger}) if plugin.rejection_reason else None,
    )
    foot = tag(
        "div",
        escape(
            " · ".join(
                part
                for part in (
                    plugin.category,
                    f"requires {', '.join(plugin.requires)}" if plugin.requires else "",
                    f"{plugin.payload_count} payloads" if plugin.payload_count else "",
                )
                if part
            )
        ),
        class_="rs-card__foot",
    )
    accent = palette.ok if plugin.healthy and plugin.enabled else palette.neutral
    classes = "rs-card rs-card--accented" if framed else "rs-card rs-card--bare"
    return tag(
        "div",
        head + body + foot,
        class_=classes,
        style=style({"border-left-color": accent}),
    )


def target_card(palette: Palette, target: TargetView, *, framed: bool = True) -> str:
    """A configured target, with its authorization record and reachability.

    The authorization block is shown, not summarized away: a target without one cannot be scanned,
    and the operator needs to see *that* rather than discover it when the start button refuses.
    """
    reachability = badge(
        target.health.status.upper(),
        (
            outcome_colour(palette, "completed" if target.health.reachable else "failed")
            if target.health.checked_at
            else palette.neutral
        ),
    )
    scope = (
        badge("LOCAL", palette.ok, dot=False)
        if target.is_local
        else badge("NON-LOCAL", palette.warn, dot=False)
    )
    authorized = (
        badge("AUTHORIZED", palette.ok, dot=False)
        if target.authorization.present
        else badge("NO AUTHORIZATION", palette.danger, dot=False)
    )
    head = tag(
        "div",
        tag("span", escape(target.name), class_="rs-card__title")
        + tag("div", join([reachability, scope, authorized]), class_="rs-row"),
        class_="rs-row rs-row--split",
    )
    detail = key_values(
        [
            ("URL", target.url),
            ("Adapter", target.adapter),
            ("Latency", f"{target.health.latency_ms} ms" if target.health.latency_ms else ""),
            ("Capabilities", ", ".join(target.health.capabilities)),
            ("Authorized by", target.authorization.authorized_by),
            ("Reference", target.authorization.authorization_ref),
            ("Scope", target.authorization.scope),
        ]
    )
    foot = tag("div", escape(target.health.detail), class_="rs-card__foot")
    accent = palette.ok if target.enabled else palette.neutral
    return tag(
        "div",
        head + detail + foot,
        class_="rs-card rs-card--accented" if framed else "rs-card rs-card--bare",
        style=style({"border-left-color": accent}),
    )


def report_card(palette: Palette, report: ReportView, *, framed: bool = True) -> str:
    """A generated report.

    ``framed=False`` for a card inside a bordered container -- see ``summary_card``.
    """
    head = tag(
        "div",
        # The SCAN'S NAME as the heading, not the report's hex id. A report is the write-up of a
        # scan, and "vulnerable-rag standard sweep · PDF" is how an operator refers to one; the id
        # is a database key that happens to be visible. It is still shown, once, in the detail rows
        # below, where it is needed for correlating with a file on disk.
        tag("span", escape(report.label), class_="rs-card__title")
        + tag(
            "div",
            join(
                [
                    badge(report.fmt.upper(), palette.accent, dot=False),
                    grade_badge(palette, report.grade),
                    risk_badge(palette, report.risk_score),
                ]
            ),
            class_="rs-row",
        ),
        class_="rs-row rs-row--split",
    )
    detail = key_values(
        [
            ("Report id", report.id),
            ("Scan", report.scan_name or report.scan_id),
            ("Target", report.target),
            ("Generated", report.generated_at),
            ("Findings", str(report.findings_count) if report.findings_count else ""),
            ("Size", report.size_label),
        ]
    )
    foot = (
        tag("div", outcome_badge(palette, report.status), class_="rs-card__foot")
        if report.status
        else ""
    )
    return tag(
        "div",
        head + detail + foot,
        class_="rs-card" if framed else "rs-card rs-card--bare",
    )


def summary_card(
    title: str, rows: Mapping[str, str], *, footer: str = "", framed: bool = True
) -> str:
    """A generic titled key/value panel, used where a bespoke card would be over-specified.

    ``framed=False`` drops the border and margin, for a card already inside a bordered container.
    Nested borders read as a rendering bug, and the card's own margin was what pushed its visual
    edge past the space the layout had reserved -- which is how the summary came to overlap the
    action buttons beneath it.
    """
    body = key_values(list(rows.items()))
    foot = tag("div", escape(footer), class_="rs-card__foot") if footer else ""
    return tag(
        "div",
        tag("div", escape(title), class_="rs-card__title") + body + foot,
        class_="rs-card" if framed else "rs-card rs-card--bare",
    )
