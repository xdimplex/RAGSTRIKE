"""PayloadLoader tests -- JSON, YAML, TXT."""

from __future__ import annotations

from pathlib import Path

import pytest

from ragstrike.core.errors import PluginError
from ragstrike.plugins.base.payloads import PayloadLoader


def test_missing_directory_yields_empty(tmp_path: Path) -> None:
    """A plugin whose payloads are generated in code has no ``payloads/`` -- normal."""
    loader = PayloadLoader(tmp_path / "does-not-exist")

    assert loader.all() == []


def test_yaml_list_of_mappings(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text(
        "- id: one\n  content: hello\n- id: two\n  content: world\n  tier: deep\n",
        encoding="utf-8",
    )

    payloads = PayloadLoader(tmp_path).all()

    assert [p.id for p in payloads] == ["one", "two"]
    assert payloads[1].tier == "deep"


def test_yaml_top_level_payloads_key(tmp_path: Path) -> None:
    """The other accepted shape -- mirroring Annex B's payload-set schema."""
    (tmp_path / "set.yaml").write_text(
        "id: core-en\npayloads:\n  - id: p1\n    template: 'hello'\n",
        encoding="utf-8",
    )

    payloads = PayloadLoader(tmp_path).all()

    assert payloads[0].id == "p1"
    assert payloads[0].content == "hello"


def test_json(tmp_path: Path) -> None:
    (tmp_path / "b.json").write_text('[{"id": "j1", "content": "from json"}]', encoding="utf-8")

    payloads = PayloadLoader(tmp_path).all()

    assert payloads[0].id == "j1"


def test_txt_one_per_line(tmp_path: Path) -> None:
    (tmp_path / "c.txt").write_text("first\n# a comment\n\nsecond\n", encoding="utf-8")

    payloads = PayloadLoader(tmp_path).all()

    assert [p.content for p in payloads] == ["first", "second"]


def test_filename_order_is_preserved(tmp_path: Path) -> None:
    """Payload sequences must stay reproducible: scoring treats successes/attempts as a
    measurement, and a reordered sequence is a different measurement."""
    for name in ("c.yaml", "a.yaml", "b.yaml"):
        (tmp_path / name).write_text(f"- id: {name}\n  content: {name}\n", encoding="utf-8")

    payloads = PayloadLoader(tmp_path).all()

    assert [p.id for p in payloads] == ["a.yaml", "b.yaml", "c.yaml"]


def test_unsupported_extensions_are_ignored(tmp_path: Path) -> None:
    """A plugin can drop a README next to its payloads without confusing the loader."""
    (tmp_path / "README.md").write_text("not a payload", encoding="utf-8")
    (tmp_path / "a.yaml").write_text("- id: x\n  content: y\n", encoding="utf-8")

    assert len(PayloadLoader(tmp_path).all()) == 1


def test_malformed_yaml_is_a_plugin_error(tmp_path: Path) -> None:
    (tmp_path / "bad.yaml").write_text("- id: broken\n  content: [unclosed\n", encoding="utf-8")

    with pytest.raises(PluginError):
        PayloadLoader(tmp_path).all()


def test_payload_without_content_is_refused(tmp_path: Path) -> None:
    """Silent skip would be indistinguishable from an empty payload set."""
    (tmp_path / "bad.yaml").write_text("- id: x\n  tier: quick\n", encoding="utf-8")

    with pytest.raises(PluginError):
        PayloadLoader(tmp_path).all()
