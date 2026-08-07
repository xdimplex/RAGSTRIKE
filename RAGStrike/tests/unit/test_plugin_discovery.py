"""Plugin discovery tests.

The claim under test is the one the whole framework rests on: **drop a directory into ``plugins/``
and it is found, with no registration anywhere.** These tests write real directories to disk rather
than mocking discovery, because a mock would happily confirm a claim that is false on a real
filesystem.

``test_no_plugin_name_appears_in_the_engine`` is the guard on that claim. If a slug ever gets
hardcoded into the engine, the plugin system has quietly become a lookup table.
"""

from __future__ import annotations

import ast
from pathlib import Path

from ragstrike import PLUGIN_API_VERSION
from ragstrike.core.config.models import PluginSettings
from ragstrike.plugins.registry.plugin_registry import PluginRegistry


def registry_for(directory: Path, **overrides) -> PluginRegistry:
    settings = PluginSettings(local_dirs=[directory], **overrides)
    return PluginRegistry(settings, api_version=PLUGIN_API_VERSION)


def test_a_dropped_in_directory_is_discovered(make_plugin) -> None:
    """The defining property of the plugin system."""
    plugins_dir = make_plugin("fixture-attack")

    health = registry_for(plugins_dir).discover()

    assert [p.slug for p in health.active] == ["fixture-attack"]
    assert health.rejected == []


def test_multiple_plugins_are_all_discovered(make_plugin) -> None:
    plugins_dir = make_plugin("alpha-attack")
    make_plugin("beta-attack", directory=plugins_dir)

    health = registry_for(plugins_dir).discover()

    assert sorted(p.slug for p in health.active) == ["alpha-attack", "beta-attack"]


def test_inventory_maps_slug_to_version(make_plugin) -> None:
    plugins_dir = make_plugin("fixture-attack", version="2.3.4")

    assert registry_for(plugins_dir).discover().inventory == {"fixture-attack": "2.3.4"}


def test_metadata_is_read_from_the_loaded_class(make_plugin) -> None:
    plugins_dir = make_plugin("fixture-attack")

    plugin = registry_for(plugins_dir).discover().active[0]

    assert plugin.metadata().slug == "fixture-attack"
    assert plugin.metadata().category == "fixture"


def test_empty_directory_yields_no_plugins(tmp_path: Path) -> None:
    (tmp_path / "plugins").mkdir()

    health = registry_for(tmp_path / "plugins").discover()

    assert health.active == []
    assert health.rejected == []


def test_missing_directory_is_not_an_error(tmp_path: Path) -> None:
    """A configured directory that does not exist is normal, not a failure."""
    health = registry_for(tmp_path / "does-not-exist").discover()

    assert health.active == []


def test_directory_without_a_manifest_is_ignored(tmp_path: Path) -> None:
    stray = tmp_path / "plugins" / "not_a_plugin"
    stray.mkdir(parents=True)
    (stray / "readme.txt").write_text("just a folder", encoding="utf-8")

    assert registry_for(tmp_path / "plugins").discover().active == []


# ------------------------------------------------------------------------------------------------
# Failure isolation -- a broken plugin must never stop the scan
# ------------------------------------------------------------------------------------------------


def test_a_broken_manifest_is_skipped_not_fatal(make_plugin) -> None:
    plugins_dir = make_plugin("good-attack")
    make_plugin("broken-attack", directory=plugins_dir, broken_manifest=True)

    health = registry_for(plugins_dir).discover()

    assert [p.slug for p in health.active] == ["good-attack"]


def test_a_plugin_that_fails_to_import_is_rejected_with_a_reason(make_plugin) -> None:
    plugins_dir = make_plugin("good-attack")
    make_plugin("exploding-attack", directory=plugins_dir, broken_code=True)

    health = registry_for(plugins_dir).discover()

    assert [p.slug for p in health.active] == ["good-attack"]
    rejected = [r for r in health.rejected if r.slug == "exploding-attack"]
    assert rejected and rejected[0].reason == "load-failed"


def test_rejections_are_never_silent(make_plugin) -> None:
    """Every refusal is reported. A plugin nobody hears about changes results invisibly."""
    plugins_dir = make_plugin("modern-attack", api_range=">=99.0")

    health = registry_for(plugins_dir).discover()

    assert health.active == []
    assert health.rejected[0].reason == "incompatible"
    assert "99.0" in health.rejected[0].detail


# ------------------------------------------------------------------------------------------------
# Policy
# ------------------------------------------------------------------------------------------------


def test_incompatible_api_range_is_refused(make_plugin) -> None:
    plugins_dir = make_plugin("future-attack", api_range=">=2.0,<3.0")

    assert registry_for(plugins_dir).discover().active == []


def test_disabled_plugins_are_not_loaded(make_plugin) -> None:
    plugins_dir = make_plugin("unwanted-attack")

    health = registry_for(plugins_dir, disabled=["unwanted-attack"]).discover()

    assert health.active == []
    assert health.rejected[0].reason == "disabled"


def test_elevated_permissions_are_refused_by_default(make_plugin) -> None:
    """v1 does not sandbox; it refuses. Stated honestly rather than implying isolation."""
    plugins_dir = make_plugin("greedy-attack", network=True)

    health = registry_for(plugins_dir).discover()

    assert health.active == []
    assert health.rejected[0].reason == "elevated-permissions"
    assert "network egress" in health.rejected[0].detail


def test_elevated_permissions_are_allowed_when_opted_in(make_plugin) -> None:
    plugins_dir = make_plugin("greedy-attack", network=True)

    health = registry_for(plugins_dir, allow_elevated_permissions=True).discover()

    assert [p.slug for p in health.active] == ["greedy-attack"]


def test_duplicate_slugs_resolve_by_version_and_record_the_loser(make_plugin, tmp_path) -> None:
    """Silent shadowing would change scan results with no visible symptom."""
    first = make_plugin("clash-attack", version="1.0.0", directory=tmp_path / "dir_a")
    second = make_plugin("clash-attack", version="2.0.0", directory=tmp_path / "dir_b")

    settings = PluginSettings(local_dirs=[first, second])
    health = PluginRegistry(settings, api_version=PLUGIN_API_VERSION).discover()

    assert [(p.slug, p.version) for p in health.active] == [("clash-attack", "2.0.0")]
    assert any(r.reason == "shadowed" for r in health.rejected)


def test_discovery_is_idempotent(make_plugin) -> None:
    """Repeated discovery must not import third-party code twice and produce two class objects."""
    registry = registry_for(make_plugin("fixture-attack"))

    first = registry.discover()
    second = registry.discover()

    assert first.active[0] is second.active[0]


# ------------------------------------------------------------------------------------------------
# The guard
# ------------------------------------------------------------------------------------------------


def test_no_plugin_name_appears_in_engine_code() -> None:
    """No plugin name may appear in *executable* code under ``src/ragstrike``.

    The moment one does, the plugin system has become a lookup table with extra steps and the
    zero-core-edit promise is no longer true.

    Docstrings and comments are excluded deliberately: pointing a reader at the reference plugin is
    documentation, not coupling. The check walks the AST and inspects only identifiers and non-
    docstring string literals, so a mention in prose passes and a mention in a dict key does not.
    """
    engine = Path(__file__).resolve().parents[2] / "src" / "ragstrike"
    forbidden = ("dummy-attack", "dummy_attack", "DummyAttack")
    offenders: list[str] = []

    for path in engine.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = {
            ast.get_docstring(node, clean=False)
            for node in ast.walk(tree)
            if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in docstrings:
                    continue
                hits = [token for token in forbidden if token in node.value]
            elif isinstance(node, ast.Name | ast.Attribute):
                identifier = node.id if isinstance(node, ast.Name) else node.attr
                hits = [token for token in forbidden if token == identifier]
            else:
                continue

            offenders += [f"{path.relative_to(engine)}:{node.lineno} -> {t}" for t in hits]

    assert not offenders, f"plugin names hardcoded in engine code: {offenders}"
