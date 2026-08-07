"""Reusable UI components.

Every component in this package is a **pure function that returns a string of HTML**, except the
three in :mod:`~ragstrike.dashboard.components.controls` that need real Streamlit widgets. That is
not an aesthetic preference: it is what makes the component tests assert on markup rather than on
screenshots, and it is what lets the whole library be imported in an environment with no Streamlit.

The sixteen components the brief names map onto these modules:

===========================  =====================================================================
Component                    Module
===========================  =====================================================================
Status Card                  :func:`~ragstrike.dashboard.components.cards.status_card`
Metric Card                  :func:`~ragstrike.dashboard.components.cards.metric_card`
Progress Bar                 :func:`~ragstrike.dashboard.components.progress.progress_bar`
Plugin Card                  :func:`~ragstrike.dashboard.components.cards.plugin_card`
Target Card                  :func:`~ragstrike.dashboard.components.cards.target_card`
Report Card                  :func:`~ragstrike.dashboard.components.cards.report_card`
Risk Badge                   :func:`~ragstrike.dashboard.components.badges.risk_badge`
Severity Badge               :func:`~ragstrike.dashboard.components.badges.severity_badge`
Log Viewer                   :func:`~ragstrike.dashboard.components.log_viewer.log_viewer`
Timeline                     :func:`~ragstrike.dashboard.components.timeline.timeline`
Search Bar                   :func:`~ragstrike.dashboard.components.controls.search_bar`
Filter Panel                 :func:`~ragstrike.dashboard.components.controls.filter_panel`
Confirmation Dialog          :func:`~ragstrike.dashboard.components.controls.confirmation_dialog`
Notification Toast           :func:`~ragstrike.dashboard.components.feedback.toast`
Loading Overlay              :func:`~ragstrike.dashboard.components.feedback.loading_overlay`
Empty State                  :func:`~ragstrike.dashboard.components.feedback.empty_state`
===========================  =====================================================================
"""

from ragstrike.dashboard.components.badges import (
    badge,
    grade_badge,
    grade_hero,
    outcome_badge,
    risk_badge,
    risk_band,
    severity_badge,
)
from ragstrike.dashboard.components.cards import (
    key_values,
    metric_card,
    plugin_card,
    report_card,
    status_card,
    summary_card,
    target_card,
)
from ragstrike.dashboard.components.feedback import (
    banner,
    empty_state,
    error_panel,
    loading_overlay,
    render_exception,
    toast,
)
from ragstrike.dashboard.components.html import escape, join, style, tag
from ragstrike.dashboard.components.log_viewer import log_viewer
from ragstrike.dashboard.components.progress import (
    format_duration,
    progress_bar,
    scan_progress,
    severity_bars,
)
from ragstrike.dashboard.components.timeline import TimelineEvent, timeline

__all__ = [
    "TimelineEvent",
    "badge",
    "banner",
    "empty_state",
    "error_panel",
    "escape",
    "format_duration",
    "grade_badge",
    "grade_hero",
    "join",
    "key_values",
    "loading_overlay",
    "log_viewer",
    "metric_card",
    "outcome_badge",
    "plugin_card",
    "progress_bar",
    "render_exception",
    "report_card",
    "risk_badge",
    "risk_band",
    "scan_progress",
    "severity_badge",
    "severity_bars",
    "status_card",
    "style",
    "summary_card",
    "tag",
    "target_card",
    "timeline",
    "toast",
]
