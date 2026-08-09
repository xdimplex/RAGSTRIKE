"""Interactive controls: search bar, filter panel, confirmation dialog.

WHY STREAMLIT IS IMPORTED INSIDE THE FUNCTIONS
    Everything else in ``components/`` is a pure string builder and imports nothing from Streamlit.
    These three need real widgets. Importing Streamlit lazily keeps the whole package importable --
    and therefore testable -- without it, and it keeps the *decision logic* in this module (which
    facets exist, what a confirmation is asking) separate from the rendering, so the interesting
    half is still covered by a plain unit test.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from ragstrike.dashboard.services.filters import FilterState
from ragstrike.dashboard.state.persistence import durable_multi, durable_slider, durable_text

#: Which facets a page offers. Not every page has every facet -- a plugin list has no date -- and
#: rendering an inert control is worse than rendering none.
FACETS = ("severity", "status", "category", "plugin", "target", "date", "risk")


@dataclass(frozen=True, slots=True)
class FacetOptions:
    """The choices available in one filter panel, derived from the rows on screen.

    Derived from the rows rather than hardcoded: a filter offering ``context_poisoning`` on a page
    with no context-poisoning rows is a dead end the operator has to discover by clicking it.
    """

    severities: tuple[str, ...] = ()
    statuses: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    plugins: tuple[str, ...] = ()
    targets: tuple[str, ...] = ()


def facet_options(rows: Sequence[object]) -> FacetOptions:
    """Collect the distinct values present in a row set."""

    def distinct(*names: str) -> tuple[str, ...]:
        values: set[str] = set()
        for row in rows:
            for name in names:
                value = getattr(row, name, None)
                if value:
                    values.add(str(value))
                    break
        return tuple(sorted(values))

    return FacetOptions(
        severities=distinct("severity"),
        statuses=distinct("status", "state", "outcome"),
        categories=distinct("category"),
        plugins=distinct("plugin", "slug"),
        targets=distinct("target"),
    )


def confirmation_prompt(action: str, subject: str) -> str:
    """The sentence a destructive action must show before it happens.

    Names the action *and* the subject. "Are you sure?" is the dialog people click through; "Delete
    report rep-0004?" is the one they read.
    """
    return f"{action} {subject}? This cannot be undone."


# -------------------------------------------------------------------------------------------------
# Streamlit renderers
# -------------------------------------------------------------------------------------------------


def search_bar(*, key: str, value: str = "", placeholder: str = "Search...") -> str:
    """A search input. Returns the current query."""
    import streamlit as st

    result = st.text_input(
        "Search",
        value=value,
        key=key,
        placeholder=placeholder,
        label_visibility="collapsed",
    )
    return str(result or "")


def filter_panel(
    state: FilterState,
    options: FacetOptions,
    *,
    key: str,
    facets: Sequence[str] = FACETS,
) -> FilterState:
    """Render the facets a page asked for and return the new filter state.

    Returns a *new* state rather than mutating: Streamlit re-runs the script top to bottom, and a
    filter mutated in place is a filter that can be observed half-applied by whatever renders above
    the panel.
    """

    text = state.text
    severities = state.severities
    statuses = state.statuses
    categories = state.categories
    plugins = state.plugins
    targets = state.targets
    date_from = state.date_from
    date_to = state.date_to
    min_risk = state.min_risk
    max_risk = state.max_risk

    # EVERY control here is a `durable_*` one.
    #
    # These are the filters an operator sets up and then leaves in place while they work. As plain
    # widgets they were destroyed the moment the section changed -- Streamlit discards a widget's
    # state on any run that does not render it -- so coming back to Scan History showed an unfiltered
    # table that the panel still claimed was filtered. A refresh lost them as well.
    if "severity" in facets and options.severities:
        severities = tuple(
            durable_multi(
                "Severity", options.severities, f"{key}.sev", default=list(severities)
            )
        )
    if "status" in facets and options.statuses:
        statuses = tuple(
            durable_multi("Status", options.statuses, f"{key}.status", default=list(statuses))
        )
    if "category" in facets and options.categories:
        categories = tuple(
            durable_multi("Category", options.categories, f"{key}.cat", default=list(categories))
        )
    if "plugin" in facets and options.plugins:
        plugins = tuple(
            durable_multi("Plugin", options.plugins, f"{key}.plugin", default=list(plugins))
        )
    if "target" in facets and options.targets:
        targets = tuple(
            durable_multi("Target", options.targets, f"{key}.target", default=list(targets))
        )
    if "date" in facets:
        date_from = durable_text("From (YYYY-MM-DD)", f"{key}.from")
        date_to = durable_text("To (YYYY-MM-DD)", f"{key}.to")
    if "risk" in facets:
        low, high = durable_slider(
            "Risk score",
            f"{key}.risk",
            default=(float(min_risk), float(max_risk)),
            min_value=0.0,
            max_value=100.0,
        )
        min_risk, max_risk = float(low), float(high)

    return FilterState(
        text=text,
        severities=severities,
        statuses=statuses,
        categories=categories,
        plugins=plugins,
        targets=targets,
        date_from=date_from,
        date_to=date_to,
        min_risk=min_risk,
        max_risk=max_risk,
    )


def confirmation_dialog(
    *,
    key: str,
    action: str,
    subject: str,
    state: Any,
) -> bool:
    """A two-step confirm for a destructive action. Returns True only on the second click.

    The pending flag lives in centralized state rather than in a local variable, because Streamlit
    discards local variables between re-runs -- which is precisely the property that would turn a
    "confirm delete" into a one-click delete.
    """
    import streamlit as st

    if state.pending_confirmation(key) is None:
        if st.button(action, key=f"{key}.request", type="secondary"):
            state.request_confirmation(key, subject)
            st.rerun()
        return False

    st.warning(confirmation_prompt(action, subject))
    confirm, cancel = st.columns(2)
    if confirm.button("Confirm", key=f"{key}.confirm", type="primary"):
        state.resolve_confirmation(key)
        return True
    if cancel.button("Cancel", key=f"{key}.cancel"):
        state.resolve_confirmation(key)
        st.rerun()
    return False
