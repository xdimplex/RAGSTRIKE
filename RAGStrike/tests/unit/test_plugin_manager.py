"""PluginManager tests -- CLI-facing operations."""

from __future__ import annotations

from pathlib import Path

import pytest

from ragstrike import PLUGIN_API_VERSION
from ragstrike.core.config.models import PluginSettings
from ragstrike.plugins.registry.plugin_config import load_plugin_config
from ragstrike.plugins.registry.plugin_manager import PluginManager
from ragstrike.plugins.registry.plugin_registry import PluginRegistry


@pytest.fixture
def manager(make_plugin, tmp_path: Path) -> PluginManager:
    plugins_dir = make_plugin("fixture-attack")
    settings = PluginSettings(local_dirs=[plugins_dir])
    registry = PluginRegistry(
        settings,
        api_version=PLUGIN_API_VERSION,
        plugin_config_path=tmp_path / "plugins.yaml",
    )
    return PluginManager(registry)


def test_list_returns_a_summary_per_plugin(manager: PluginManager) -> None:
    summaries = manager.summaries()

    assert any(s.slug == "fixture-attack" for s in summaries)


def test_info_for_known_plugin(manager: PluginManager) -> None:
    info = manager.info("fixture-attack")

    assert info is not None
    assert info.summary.slug == "fixture-attack"


def test_info_for_unknown_plugin_returns_none(manager: PluginManager) -> None:
    assert manager.info("no-such-thing") is None


def test_disable_persists_to_plugins_yaml(manager: PluginManager, tmp_path: Path) -> None:
    manager.disable("fixture-attack")

    reloaded = load_plugin_config(tmp_path / "plugins.yaml")
    assert reloaded.is_disabled("fixture-attack")


def test_disabled_plugin_is_refused_on_next_discovery(make_plugin, tmp_path: Path) -> None:
    """The whole point of ``disable`` -- future scans do not schedule the plugin."""
    plugins_dir = make_plugin("fixture-attack")
    config = tmp_path / "plugins.yaml"

    # First manager: disable and persist.
    registry1 = PluginRegistry(
        PluginSettings(local_dirs=[plugins_dir]),
        api_version=PLUGIN_API_VERSION,
        plugin_config_path=config,
    )
    PluginManager(registry1).disable("fixture-attack")

    # Second manager: fresh discovery, should refuse the plugin.
    registry2 = PluginRegistry(
        PluginSettings(local_dirs=[plugins_dir]),
        api_version=PLUGIN_API_VERSION,
        plugin_config_path=config,
    )
    health = registry2.discover()

    assert health.active == []
    assert any(r.reason == "disabled-in-config" for r in health.rejected)


def test_validate_returns_reports_per_plugin(manager: PluginManager) -> None:
    reports = manager.validate()

    assert reports
    for slug, report in reports:
        assert slug
        assert report.checks


def test_reload_returns_fresh_health(manager: PluginManager) -> None:
    health = manager.reload()

    assert len(health.active) >= 1
