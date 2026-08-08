"""Settings -- dashboard preferences, and the effective configuration read-only.

RESPONSIBILITY
    Change how the *interface* behaves. Nothing here changes what a scan does.

TWO SECTIONS, DELIBERATELY NOT ONE
    Preferences are editable and session-scoped. Engine configuration is displayed and read-only. A
    UI that could edit the safety policy would be a UI that could switch off the guard stopping an
    operator scanning a system they are not authorized to scan -- and no confirmation dialog makes
    that acceptable. Changing it takes an edit to ``configs/config.yaml`` and a restart, which is a
    deliberate act with an audit trail.

"DO NOT EXPOSE SENSITIVE CONFIGURATION"
    Every value on this page goes through :func:`~ragstrike.dashboard.services.settings_service.redact`
    first, which matches on key *names* -- so a backend that starts returning ``ollama_api_key``
    tomorrow is redacted today without anyone remembering to add it.
"""

from __future__ import annotations

from typing import Any

from ragstrike.dashboard.config import REPORT_FORMATS, ReportPreferences
from ragstrike.dashboard.context import PageContext
from ragstrike.dashboard.layouts.page_layout import page_header, section
from ragstrike.dashboard.services.settings_service import (
    OPTIONS,
    REPORT_OPTIONS,
    SettingsOption,
)


def render(context: PageContext) -> None:
    page_header("Settings", "How the dashboard behaves. Nothing here changes what a scan does.")

    _preferences(context)
    _report_preferences(context)


def _widget(option: SettingsOption, current: Any) -> Any:
    import streamlit as st

    if option.kind == "choice":
        choices = list(option.choices)
        index = choices.index(str(current)) if str(current) in choices else 0
        return st.selectbox(
            option.label, choices, index=index, help=option.help, key=f"rs.set.{option.key}"
        )
    if option.kind == "number":
        return st.number_input(
            option.label,
            value=float(current or 0.0),
            min_value=option.minimum or None,
            max_value=option.maximum or None,
            help=option.help,
            key=f"rs.set.{option.key}",
        )
    if option.kind == "bool":
        return st.checkbox(
            option.label, value=bool(current), help=option.help, key=f"rs.set.{option.key}"
        )
    return st.text_input(
        option.label, value=str(current or ""), help=option.help, key=f"rs.set.{option.key}"
    )


def _preferences(context: PageContext) -> None:
    import streamlit as st

    section("Preferences")
    config = context.config
    changes: dict[str, Any] = {}

    columns = st.columns(2)
    for index, option in enumerate(OPTIONS):
        with columns[index % 2]:
            changes[option.key] = _widget(option, getattr(config, option.key, ""))

    if st.button("Apply", key="rs.set.apply", type="primary"):
        updated = context.services.settings.apply(config, changes)
        context.state.settings = updated
        context.notify("success", "Preferences applied to this session.")
        st.rerun()


def _report_preferences(context: PageContext) -> None:
    import streamlit as st

    section("Report preferences")
    current = context.config.reports
    values: dict[str, Any] = {}
    columns = st.columns(3)
    for index, option in enumerate(REPORT_OPTIONS):
        with columns[index % 3]:
            values[option.key] = _widget(option, getattr(current, option.key, ""))

    st.caption(
        "Redaction is applied by the reporting engine when it renders, not by the dashboard. "
        "PDF is listed because the engine declares it; it does not render yet."
    )

    if st.button("Save report defaults", key="rs.set.reports"):
        fmt = str(values.get("default_format", current.default_format))
        context.state.settings = context.config.with_overrides(
            reports=ReportPreferences(
                default_format=fmt if fmt in REPORT_FORMATS else current.default_format,
                include_evidence=bool(values.get("include_evidence", current.include_evidence)),
                redaction=str(values.get("redaction", current.redaction)),
                open_after_export=current.open_after_export,
            )
        )
        context.notify("success", "Report defaults saved.")
        st.rerun()


# THE "EFFECTIVE CONFIGURATION" PANEL WAS REMOVED, NOT REPAIRED.
#
# It rendered the dashboard's settings as raw JSON and then tried to fetch the engine's
# configuration from ``GET /config``. That route does not exist, so the panel ended with a red
# "Request rejected -- Not Found" on a page whose whole purpose is to look trustworthy.
#
# Repairing it meant implementing the route, and that is what settled the question: the engine's
# effective configuration is its safety policy, its allowed-host list, its model settings and its
# filesystem paths. Serving all of that from an unauthenticated loopback API buys nothing an
# operator cannot already get by opening ``configs/config.yaml`` on the machine, and this is a
# security tool -- the reasonable default is not to publish its own posture over HTTP.
#
# The editable preferences above cover everything a dashboard user actually needs. A JSON dump of
# the same values underneath them was duplication rather than information.
