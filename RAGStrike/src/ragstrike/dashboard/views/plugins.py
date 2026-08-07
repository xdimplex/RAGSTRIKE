"""Plugins -- the installed inventory, and the four operations the brief names.

RESPONSIBILITY
    Show what is installed, what was refused and why, and let an operator enable, disable, reload,
    or validate a plugin.

"DO NOT EDIT PLUGIN CODE"
    Nothing on this page can. Enable and disable are state changes the backend writes to
    ``configs/plugins.yaml`` through the PluginManager -- the single place plugin state is mutated
    anywhere in the system. Validate is read-only. There is no editor, and no endpoint that would
    accept one.

WHY REFUSED PLUGINS ARE SHOWN RATHER THAN HIDDEN
    A plugin refused for requesting elevated permissions is the framework working correctly. Hiding
    it would leave the operator wondering why a pack they installed never runs.
"""

from __future__ import annotations

from collections.abc import Sequence

from ragstrike.dashboard.components.cards import plugin_card, summary_card
from ragstrike.dashboard.components.controls import facet_options, filter_panel
from ragstrike.dashboard.components.feedback import empty_state, render_exception
from ragstrike.dashboard.context import PageContext
from ragstrike.dashboard.layouts.page_layout import html, page_header, section
from ragstrike.dashboard.services.errors import DashboardError
from ragstrike.dashboard.services.filters import FilterState, apply_filters
from ragstrike.dashboard.services.models import PluginView
from ragstrike.dashboard.widgets.tables import plugin_rows, render_table

PAGE_ID = "plugins"


def render(context: PageContext) -> None:
    page_header("Plugins", "Installed attack packs and evaluation plugins.")

    if not context.backend_online and not context.demo:
        html(empty_state("⬡", "No backend", "The plugin inventory is served by the API."))
        return

    try:
        inventory = context.services.plugins.inventory()
    except DashboardError as exc:
        html(render_exception(context.palette, exc))
        return

    _toolbar(context, inventory.all)
    plugins = _filtered(context, list(inventory.all))

    if not plugins:
        html(empty_state("⬡", "No plugins match", "Clear the filters to see the full inventory."))
        return

    _summary(inventory.all, plugins)
    _table(plugins)
    _cards(context, plugins)


def _toolbar(context: PageContext, plugins: Sequence[PluginView]) -> None:
    import streamlit as st

    columns = st.columns([3, 1])
    with columns[0]:
        query = st.text_input(
            "Search plugins",
            key="rs.plugins.search",
            placeholder="Filter by name, slug, category, or description...",
            label_visibility="collapsed",
        )
    with columns[1]:
        if st.button("Reload plugins", key="rs.plugins.reload", width="stretch"):
            _reload(context)

    stored = context.state.filters_for(PAGE_ID)
    state = stored.get("state")
    base = state if isinstance(state, FilterState) else FilterState()

    with st.expander("Filters", expanded=False):
        updated = filter_panel(
            base.with_text(str(query or "")),
            facet_options(plugins),
            key="rs.plugins.filters",
            facets=("severity", "status", "category"),
        )
    stored["state"] = updated


def _filtered(context: PageContext, plugins: list[PluginView]) -> list[PluginView]:
    stored = context.state.filters_for(PAGE_ID).get("state")
    state = stored if isinstance(stored, FilterState) else FilterState()
    return apply_filters(plugins, state)


def _summary(everything: tuple[PluginView, ...], shown: list[PluginView]) -> None:
    categories = sorted({plugin.category for plugin in everything if plugin.category})
    html(
        summary_card(
            "Inventory",
            {
                "Installed": str(len(everything)),
                "Shown": str(len(shown)),
                "Enabled": str(sum(1 for p in everything if p.enabled and p.healthy)),
                "Refused": str(sum(1 for p in everything if not p.healthy)),
                "Categories": ", ".join(categories),
            },
        )
    )


def _table(plugins: list[PluginView]) -> None:
    section("Inventory")
    render_table(plugin_rows(plugins))


def _cards(context: PageContext, plugins: list[PluginView]) -> None:
    import streamlit as st

    section("Detail")
    for plugin in plugins:
        html(plugin_card(context.palette, plugin))
        actions = st.columns(4)
        if plugin.enabled:
            if actions[0].button("Disable", key=f"rs.plg.off.{plugin.slug}"):
                _toggle(context, plugin, enable=False)
        elif actions[0].button("Enable", key=f"rs.plg.on.{plugin.slug}", type="primary"):
            _toggle(context, plugin, enable=True)

        if actions[1].button("Validate", key=f"rs.plg.val.{plugin.slug}"):
            _validate(context, plugin)
        with actions[2]:
            _metadata(context, plugin)


def _metadata(context: PageContext, plugin: PluginView) -> None:
    import streamlit as st

    with st.popover("Metadata", width="stretch"):
        try:
            detail = context.services.plugins.detail(plugin.slug)
        except DashboardError as exc:
            html(render_exception(context.palette, exc))
            return
        html(
            summary_card(
                detail.display_name,
                {
                    "Slug": detail.slug,
                    "Version": detail.version,
                    "Plugin API": detail.api_version,
                    "Author": detail.author,
                    "Category": detail.category,
                    "Severity": detail.severity,
                    "Requires": ", ".join(detail.requires),
                    "Permissions": ", ".join(detail.permissions) or "none",
                    "Attacks": str(detail.attack_count),
                    "Payloads": str(detail.payload_count),
                    "Description": detail.description,
                },
            )
        )


def _toggle(context: PageContext, plugin: PluginView, *, enable: bool) -> None:
    import streamlit as st

    service = context.services.plugins
    try:
        service.enable(plugin.slug) if enable else service.disable(plugin.slug)
    except DashboardError as exc:
        html(render_exception(context.palette, exc))
        return
    context.notify("success", f"{plugin.slug} {'enabled' if enable else 'disabled'}.")
    st.rerun()


def _validate(context: PageContext, plugin: PluginView) -> None:
    import streamlit as st

    try:
        report = context.services.plugins.validate(plugin.slug)
    except DashboardError as exc:
        html(render_exception(context.palette, exc))
        return

    if report.valid:
        context.notify("success", f"{plugin.slug} passed every validation rule.")
    else:
        context.notify(
            "error",
            f"{plugin.slug} failed validation.",
            "; ".join(f"{check.name}: {check.detail}" for check in report.failures),
        )
    st.rerun()


def _reload(context: PageContext) -> None:
    import streamlit as st

    try:
        inventory = context.services.plugins.reload()
    except DashboardError as exc:
        html(render_exception(context.palette, exc))
        return
    context.notify(
        "success",
        f"Reloaded: {len(inventory.active)} active, {len(inventory.rejected)} refused.",
    )
    st.rerun()
