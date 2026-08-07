"""ScanContext tests."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from ragstrike import __version__
from ragstrike.plugins.base.context import PluginContext
from ragstrike.sdk.context import ScanContext


def make_plugin_context(**overrides) -> PluginContext:
    defaults = {
        "plugin_id": "my-plugin",
        "source": Path("plugins/my-plugin"),
        "config": {"threshold": 5},
    }
    defaults.update(overrides)
    return PluginContext.for_plugin(**defaults)


def test_defaults_are_all_empty_or_none() -> None:
    context = ScanContext()

    assert context.configuration == {}
    assert context.target is None
    assert context.database is None
    assert context.current_plugin == ""
    assert context.scan_id == ""


def test_from_plugin_context_copies_config_and_logger() -> None:
    plugin_context = make_plugin_context()

    scan_context = ScanContext.from_plugin_context(plugin_context)

    assert scan_context.configuration == {"threshold": 5}
    assert scan_context.logger is plugin_context.logger
    assert scan_context.current_plugin == "my-plugin"


def test_from_plugin_context_is_non_destructive() -> None:
    """Building a ScanContext must not mutate the PluginContext it was built from."""
    plugin_context = make_plugin_context()
    original_config = dict(plugin_context.config)

    ScanContext.from_plugin_context(plugin_context, target=object(), scan_id="scan-1")

    assert plugin_context.config == original_config


def test_from_plugin_context_accepts_target_and_scan_id() -> None:
    plugin_context = make_plugin_context()
    fake_target = object()

    scan_context = ScanContext.from_plugin_context(
        plugin_context, target=fake_target, scan_id="scan-42"
    )

    assert scan_context.target is fake_target
    assert scan_context.scan_id == "scan-42"


def test_from_plugin_context_database_is_always_none() -> None:
    scan_context = ScanContext.from_plugin_context(make_plugin_context())

    assert scan_context.database is None


def test_framework_version_matches_the_package_version() -> None:
    assert ScanContext().framework_version == __version__


def test_configuration_dict_is_a_copy_not_the_same_object() -> None:
    plugin_context = make_plugin_context()

    scan_context = ScanContext.from_plugin_context(plugin_context)

    assert scan_context.configuration == plugin_context.config
    assert scan_context.configuration is not plugin_context.config


def test_to_dict_summarizes_target_and_database_rather_than_embedding_them() -> None:
    scan_context = ScanContext.from_plugin_context(
        make_plugin_context(), target=object(), scan_id="scan-1"
    )

    snapshot = scan_context.to_dict()

    assert isinstance(snapshot["target"], str)  # repr(), not the object itself
    assert snapshot["database_available"] is False
    assert snapshot["scan_id"] == "scan-1"
    assert snapshot["current_plugin"] == "my-plugin"


def test_to_dict_target_is_none_when_unset() -> None:
    assert ScanContext().to_dict()["target"] is None


def test_is_frozen() -> None:
    context = ScanContext()

    with pytest.raises(dataclasses.FrozenInstanceError):
        context.current_plugin = "changed"
