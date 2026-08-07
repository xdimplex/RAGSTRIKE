"""Widgets -- composite views built from components plus a charting or tabular library.

THE LINE BETWEEN `components/` AND `widgets/`
    A *component* returns a string and depends on nothing but the theme. A *widget* may reach for
    pandas, Altair, or a Streamlit container to render something a string cannot: a chart, a sortable
    dataframe, a two-column detail drawer.

    The split matters because it keeps the dependency-heavy half small. Sixteen components import
    nothing; four widgets import pandas. If a future maintainer wants to drop Altair, the blast
    radius is this package.

TESTABILITY
    Every widget separates *shaping the data* from *drawing it*. The shaping functions are pure,
    return plain lists of dictionaries, and are what the tests exercise. Drawing is a thin call the
    integration tests reach through ``AppTest``.
"""

from ragstrike.dashboard.widgets.charts import (
    render_severity_chart,
    render_trend_chart,
    severity_frame,
    trend_frame,
)
from ragstrike.dashboard.widgets.tables import (
    findings_rows,
    plugin_rows,
    render_table,
    report_rows,
    scan_rows,
)

__all__ = [
    "findings_rows",
    "plugin_rows",
    "render_severity_chart",
    "render_table",
    "render_trend_chart",
    "report_rows",
    "scan_rows",
    "severity_frame",
    "trend_frame",
]
