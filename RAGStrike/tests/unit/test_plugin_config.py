"""plugins.yaml loading and round-tripping."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ragstrike.core.errors import ConfigurationError
from ragstrike.plugins.registry.plugin_config import load_plugin_config


def write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_missing_file_yields_an_empty_store(tmp_path: Path) -> None:
    """Most operators never edit ``plugins.yaml``. Missing is normal, not an error."""
    store = load_plugin_config(tmp_path / "plugins.yaml")

    assert store.entries == {}
    assert store.slugs() == []


def test_reads_enable_timeout_severity_and_config(tmp_path: Path) -> None:
    path = write(
        tmp_path / "plugins.yaml",
        """
version: 1
plugins:
  fixture-attack:
    enabled: false
    timeout: 30
    severity_override: HIGH
    config:
      question: "override"
""",
    )

    entry = load_plugin_config(path).for_plugin("fixture-attack")

    assert entry.enabled is False
    assert entry.timeout_s == 30
    assert entry.severity_override == "HIGH"
    assert entry.config == {"question": "override"}


def test_absent_plugin_returns_default_entry(tmp_path: Path) -> None:
    entry = load_plugin_config(tmp_path / "plugins.yaml").for_plugin("nope")

    assert entry.enabled is None
    assert entry.timeout_s is None
    assert entry.severity_override is None


def test_disabled_is_detected(tmp_path: Path) -> None:
    path = write(
        tmp_path / "plugins.yaml",
        "version: 1\nplugins:\n  x:\n    enabled: false\n",
    )

    store = load_plugin_config(path)

    assert store.is_disabled("x") is True
    assert store.is_disabled("y") is False


def test_save_round_trips(tmp_path: Path) -> None:
    """Enable-then-save must produce a file the loader reads back to the same state."""
    path = tmp_path / "plugins.yaml"
    store = load_plugin_config(path)
    store.set_enabled("fixture-attack", False)
    store.save()

    reloaded = load_plugin_config(path)

    assert reloaded.is_disabled("fixture-attack") is True
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert parsed["plugins"]["fixture-attack"] == {"enabled": False}


def test_save_omits_unset_fields(tmp_path: Path) -> None:
    """A plugin whose only override is ``enabled: false`` must not gain empty timeout/severity
    fields it never declared. Otherwise every enable/disable rewrites the whole plugin block."""
    path = tmp_path / "plugins.yaml"
    store = load_plugin_config(path)
    store.set_enabled("x", True)
    store.save()

    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert parsed["plugins"]["x"] == {"enabled": True}


def test_malformed_yaml_is_a_configuration_error(tmp_path: Path) -> None:
    path = write(tmp_path / "plugins.yaml", "plugins: [unclosed\n")

    with pytest.raises(ConfigurationError) as caught:
        load_plugin_config(path)

    assert "YAML" in caught.value.message


def test_plugins_key_must_be_a_mapping(tmp_path: Path) -> None:
    path = write(tmp_path / "plugins.yaml", "version: 1\nplugins:\n  - just-a-string\n")

    with pytest.raises(ConfigurationError) as caught:
        load_plugin_config(path)

    assert "plugins" in caught.value.message
