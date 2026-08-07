"""Validator tests -- structure, manifest, class."""

from __future__ import annotations

from pathlib import Path

from ragstrike import PLUGIN_API_VERSION
from ragstrike.plugins.loader.manifest import parse_manifest
from ragstrike.plugins.registry.validator import (
    validate_class,
    validate_manifest,
    validate_structure,
)

# ------------------------------------------------------------------------------------------------
# Structure
# ------------------------------------------------------------------------------------------------


def test_missing_directory_fails_the_folder_check(tmp_path: Path) -> None:
    report = validate_structure(tmp_path / "does-not-exist")

    assert not report.valid
    assert any(check.rule == "folder-exists" and check.failed for check in report.checks)


def test_missing_manifest_fails_the_manifest_check(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "empty"
    plugin_dir.mkdir()

    report = validate_structure(plugin_dir)

    assert not report.valid
    assert any(check.rule == "manifest-exists" and check.failed for check in report.checks)


def test_missing_payloads_folder_fails(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "minimal"
    plugin_dir.mkdir()
    (plugin_dir / "metadata.yaml").write_text(
        "plugin:\n  slug: x\n  version: 1.0.0\n  entry_point: 'p:X'\n", encoding="utf-8"
    )

    report = validate_structure(plugin_dir)

    assert any(check.rule == "has-payloads" and check.failed for check in report.checks)


def test_well_formed_plugin_passes_structure(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "good"
    plugin_dir.mkdir()
    (plugin_dir / "metadata.yaml").write_text(
        "plugin:\n  slug: x\n  version: 1.0.0\n  entry_point: 'p:X'\n", encoding="utf-8"
    )
    (plugin_dir / "payloads").mkdir()

    assert validate_structure(plugin_dir).valid


# ------------------------------------------------------------------------------------------------
# Manifest
# ------------------------------------------------------------------------------------------------


def test_manifest_api_compatibility_check(tmp_path: Path) -> None:
    manifest_path = tmp_path / "metadata.yaml"
    manifest_path.write_text(
        """
plugin:
  slug: future-attack
  version: 1.0.0
  entry_point: 'p:X'
compatibility:
  ragstrike_api: '>=99.0'
""",
        encoding="utf-8",
    )
    manifest = parse_manifest(manifest_path)

    report = validate_manifest(manifest, api_version=PLUGIN_API_VERSION)

    assert not report.valid
    assert any(check.rule == "api-compatible" and check.failed for check in report.checks)


def test_manifest_invalid_version_string(tmp_path: Path) -> None:
    manifest_path = tmp_path / "metadata.yaml"
    manifest_path.write_text(
        "plugin:\n  slug: x\n  version: 'not-a-version'\n  entry_point: 'p:X'\n",
        encoding="utf-8",
    )
    manifest = parse_manifest(manifest_path)

    report = validate_manifest(manifest, api_version=PLUGIN_API_VERSION)

    assert any(check.rule == "version-parseable" and check.failed for check in report.checks)


# ------------------------------------------------------------------------------------------------
# Class
# ------------------------------------------------------------------------------------------------


def test_non_base_attack_class_fails(tmp_path: Path) -> None:
    class NotAttack:
        pass

    report = validate_class(NotAttack)  # type: ignore[arg-type]

    assert not report.valid
    assert any(check.rule == "inherits-base-attack" and check.failed for check in report.checks)


def test_base_attack_subclass_missing_methods_is_flagged() -> None:
    """A subclass that leaves abstractmethods unimplemented reports each missing method."""
    from ragstrike.plugins.base.attack import BaseAttack

    class Incomplete(BaseAttack):
        plugin_id = "incomplete"

    report = validate_class(Incomplete)

    assert not report.valid
    failed = {check.rule for check in report.failures}
    assert "implements-execute" in failed
    assert "implements-analyze" in failed


def test_complete_subclass_passes() -> None:
    from ragstrike.models.values.enums import PluginOutcome
    from ragstrike.plugins.base.attack import (
        Analysis,
        BaseAttack,
        Payload,
        Recommendation,
    )

    class Complete(BaseAttack):
        plugin_id = "complete"
        plugin_version = "1.0.0"

        def payloads(self):
            return [Payload(id="p", content="c")]

        async def execute(self, target, payloads):
            return []

        def analyze(self, records):
            return Analysis(outcome=PluginOutcome.PASS, summary="")

        def recommendation(self, analysis):
            return Recommendation(title="", remediation="")

    assert validate_class(Complete).valid
