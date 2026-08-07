"""Configuration and target loading tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.conftest import write_targets_yaml

from ragstrike.core.config.loader import load_settings, load_targets, select_target
from ragstrike.core.errors import ConfigurationError, TargetNotFoundError
from ragstrike.models.values.enums import Capability

# ------------------------------------------------------------------------------------------------
# Engine configuration
# ------------------------------------------------------------------------------------------------


def test_defaults_apply_when_no_file_exists(lab_root: Path) -> None:
    settings = load_settings(root=lab_root)

    assert settings.engine.max_concurrency == 4
    assert settings.safety.require_authorization is True


def test_yaml_overrides_defaults(lab_root: Path) -> None:
    (lab_root / "configs" / "ragstrike.yaml").write_text(
        "version: 1\nengine:\n  max_concurrency: 9\n", encoding="utf-8"
    )

    assert load_settings(root=lab_root).engine.max_concurrency == 9


def test_partial_yaml_keeps_untouched_defaults(lab_root: Path) -> None:
    (lab_root / "configs" / "ragstrike.yaml").write_text(
        "version: 1\nengine:\n  max_concurrency: 9\n", encoding="utf-8"
    )

    settings = load_settings(root=lab_root)

    assert settings.engine.max_concurrency == 9
    assert settings.engine.probe_timeout_s == 60


def test_environment_overrides_yaml(lab_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (lab_root / "configs" / "ragstrike.yaml").write_text(
        "version: 1\nengine:\n  max_concurrency: 9\n", encoding="utf-8"
    )
    monkeypatch.setenv("RAGSTRIKE_ENGINE__MAX_CONCURRENCY", "16")

    assert load_settings(root=lab_root).engine.max_concurrency == 16


def test_environment_values_are_typed_not_strings(
    lab_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RAGSTRIKE_SAFETY__ALLOW_REMOTE_TARGETS", "true")

    assert load_settings(root=lab_root).safety.allow_remote_targets is True


def test_storage_paths_are_anchored_to_the_repo_root(lab_root: Path) -> None:
    """Paths are relative to the repository, not to wherever the CLI was launched from."""
    settings = load_settings(root=lab_root)

    assert settings.storage.database_path.is_absolute()
    assert settings.storage.database_path.is_relative_to(lab_root)


def test_invalid_value_fails_fast_naming_the_field(lab_root: Path) -> None:
    (lab_root / "configs" / "ragstrike.yaml").write_text(
        "version: 1\nengine:\n  max_concurrency: -5\n", encoding="utf-8"
    )

    with pytest.raises(ConfigurationError) as caught:
        load_settings(root=lab_root)

    assert "max_concurrency" in caught.value.message


def test_malformed_yaml_is_reported_clearly(lab_root: Path) -> None:
    (lab_root / "configs" / "ragstrike.yaml").write_text("engine: [unclosed\n", encoding="utf-8")

    with pytest.raises(ConfigurationError) as caught:
        load_settings(root=lab_root)

    assert "not valid YAML" in caught.value.message


def test_unknown_log_level_is_rejected(lab_root: Path) -> None:
    (lab_root / "configs" / "ragstrike.yaml").write_text(
        "version: 1\nlogging:\n  level: CHATTY\n", encoding="utf-8"
    )

    with pytest.raises(ConfigurationError):
        load_settings(root=lab_root)


def test_snapshot_is_json_serializable(lab_root: Path) -> None:
    """The snapshot is stored on every scan record, so history stays explicable."""
    import json

    json.dumps(load_settings(root=lab_root).snapshot())


# ------------------------------------------------------------------------------------------------
# Targets
# ------------------------------------------------------------------------------------------------


def test_targets_load_with_all_fields(lab_root: Path) -> None:
    write_targets_yaml(
        lab_root / "configs" / "targets.yaml",
        [
            {
                "name": "lab",
                "url": "http://127.0.0.1:9000",
                "adapter": "fastapi",
                "timeout": 30,
                "enabled": True,
                "capabilities": ["CHAT", "RETURN_CHUNKS"],
                "authorization": {"authorized_by": "me", "authorization_ref": "REF-1"},
            }
        ],
    )

    target = load_targets(root=lab_root)[0]

    assert target.name == "lab"
    assert target.timeout_s == 30
    assert target.capabilities == (Capability.CHAT, Capability.RETURN_CHUNKS)
    assert target.is_authorized


def test_missing_targets_file_yields_no_targets(lab_root: Path) -> None:
    assert load_targets(root=lab_root) == []


def test_target_without_url_is_rejected(lab_root: Path) -> None:
    write_targets_yaml(lab_root / "configs" / "targets.yaml", [{"name": "x", "adapter": "fastapi"}])

    with pytest.raises(ConfigurationError) as caught:
        load_targets(root=lab_root)

    assert "url" in caught.value.message


def test_incomplete_authorization_is_rejected(lab_root: Path) -> None:
    """Half an authorization record is worse than none -- it looks like accountability."""
    write_targets_yaml(
        lab_root / "configs" / "targets.yaml",
        [
            {
                "name": "x",
                "url": "http://127.0.0.1:9000",
                "adapter": "fastapi",
                "authorization": {"authorized_by": "me"},
            }
        ],
    )

    with pytest.raises(ConfigurationError) as caught:
        load_targets(root=lab_root)

    assert "authorization" in caught.value.message


def test_unknown_capability_is_rejected_with_the_valid_list(lab_root: Path) -> None:
    write_targets_yaml(
        lab_root / "configs" / "targets.yaml",
        [
            {
                "name": "x",
                "url": "http://127.0.0.1:9000",
                "adapter": "fastapi",
                "capabilities": ["TELEPATHY"],
            }
        ],
    )

    with pytest.raises(ConfigurationError) as caught:
        load_targets(root=lab_root)

    assert "CHAT" in caught.value.hint


def test_target_without_authorization_loads_but_is_unauthorized(lab_root: Path) -> None:
    """Loading is not authorizing. The engine refuses at scan time, with its own exit code."""
    write_targets_yaml(
        lab_root / "configs" / "targets.yaml",
        [{"name": "x", "url": "http://127.0.0.1:9000", "adapter": "fastapi"}],
    )

    assert load_targets(root=lab_root)[0].is_authorized is False


# ------------------------------------------------------------------------------------------------
# Selection
# ------------------------------------------------------------------------------------------------


def test_selects_by_name(authorized_target, unauthorized_target) -> None:
    chosen = select_target([authorized_target, unauthorized_target], "no-auth-target")

    assert chosen.name == "no-auth-target"


def test_selects_the_only_enabled_target_when_unnamed(authorized_target) -> None:
    assert select_target([authorized_target], None).name == authorized_target.name


def test_unknown_name_lists_what_is_available(authorized_target) -> None:
    with pytest.raises(TargetNotFoundError) as caught:
        select_target([authorized_target], "nope")

    assert "fixture-target" in caught.value.hint


def test_ambiguous_selection_requires_a_name(authorized_target, unauthorized_target) -> None:
    with pytest.raises(TargetNotFoundError) as caught:
        select_target([authorized_target, unauthorized_target], None)

    assert "--target" in caught.value.message


def test_no_enabled_targets_is_an_error() -> None:
    with pytest.raises(TargetNotFoundError):
        select_target([], None)


# ------------------------------------------------------------------------------------------------
# The configuration file name, and the Phase 16 reconciliation
# ------------------------------------------------------------------------------------------------


def test_the_documented_file_name_is_the_one_that_is_read(lab_root: Path) -> None:
    """``configs/ragstrike.yaml`` is canonical.

    Until Phase 16 the design named this file and the loader read ``config.yaml``, so editing the
    documented file changed nothing and said nothing.
    """
    (lab_root / "configs" / "ragstrike.yaml").write_text(
        "version: 1\nengine:\n  max_concurrency: 11\n", encoding="utf-8"
    )

    assert load_settings(root=lab_root).engine.max_concurrency == 11


def test_the_legacy_file_still_loads_but_warns(lab_root: Path) -> None:
    """An existing checkout keeps working, and is told why it should not stay that way."""
    (lab_root / "configs" / "config.yaml").write_text(
        "version: 1\nengine:\n  max_concurrency: 7\n", encoding="utf-8"
    )

    with pytest.warns(DeprecationWarning, match="ragstrike.yaml"):
        settings = load_settings(root=lab_root)

    assert settings.engine.max_concurrency == 7


def test_the_canonical_file_wins_when_both_exist(lab_root: Path) -> None:
    """No ambiguity, and no merge. Two files disagreeing must resolve one way, every time."""
    (lab_root / "configs" / "config.yaml").write_text(
        "version: 1\nengine:\n  max_concurrency: 7\n", encoding="utf-8"
    )
    (lab_root / "configs" / "ragstrike.yaml").write_text(
        "version: 1\nengine:\n  max_concurrency: 11\n", encoding="utf-8"
    )

    assert load_settings(root=lab_root).engine.max_concurrency == 11


def test_an_unknown_key_is_rejected_by_name(lab_root: Path) -> None:
    """A typo in configuration must fail loudly.

    Pydantic ignores unknown keys by default, so ``max_concurency`` used to be accepted, discarded,
    and the default used instead -- a scan that silently ran with settings nobody chose.
    """
    (lab_root / "configs" / "ragstrike.yaml").write_text(
        "version: 1\nengine:\n  max_concurency: 8\n", encoding="utf-8"
    )

    with pytest.raises(ConfigurationError) as caught:
        load_settings(root=lab_root)

    assert "max_concurency" in str(caught.value)


def test_retry_settings_are_modelled(lab_root: Path) -> None:
    """``engine.retry`` shipped in the design from Phase 1 and was discarded by the schema."""
    (lab_root / "configs" / "ragstrike.yaml").write_text(
        "version: 1\nengine:\n  retry:\n    max_attempts: 5\n    backoff_base_s: 0.5\n",
        encoding="utf-8",
    )

    retry = load_settings(root=lab_root).engine.retry

    assert retry.max_attempts == 5
    assert retry.backoff_base_s == 0.5
