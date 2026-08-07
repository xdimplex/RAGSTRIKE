"""CLI tests.

Driven through Typer's ``CliRunner``, so the commands, the exit codes, and the Rich rendering are
all exercised as a user would meet them.

The exit-code assertions matter more than they look. A pipeline has to be able to tell "the target
is insecure" from "the scanner is misconfigured", and collapsing both into ``1`` makes the
difference invisible to automation.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest
from tests.conftest import write_targets_yaml
from typer.testing import CliRunner

from ragstrike import PLUGIN_API_VERSION, __version__
from ragstrike.cli.exit_codes import ExitCode
from ragstrike.cli.main import app

runner = CliRunner()


@pytest.fixture
def cli_root(lab_root: Path, make_plugin) -> Path:
    """A repo root with config, a target, and one plugin -- enough for a real scan."""
    (lab_root / "configs" / "ragstrike.yaml").write_text(
        "version: 1\nlogging:\n  console: false\n", encoding="utf-8"
    )
    write_targets_yaml(
        lab_root / "configs" / "targets.yaml",
        [
            {
                "name": "lab",
                "url": "http://127.0.0.1:9000",
                "adapter": "fastapi",
                "enabled": True,
                "authorization": {"authorized_by": "tester", "authorization_ref": "TEST-1"},
            }
        ],
    )
    make_plugin("fixture-attack", directory=lab_root / "plugins")
    return lab_root


def invoke(args: list[str], root: Path):
    """Run a command with the loader's repo root pointed at *root*."""
    from ragstrike.core.config import loader

    original = loader.REPO_ROOT
    loader.REPO_ROOT = root
    try:
        return runner.invoke(app, args)
    finally:
        loader.REPO_ROOT = original


def output_of(result) -> str:
    """Everything the command printed.

    Errors are rendered to stderr on purpose, and Click's runner keeps the two streams separate, so
    a test that only reads ``stdout`` silently misses every diagnostic.
    """
    text = result.stdout or ""
    # Raises when the runner was configured with mixed streams; stdout already has everything then.
    with contextlib.suppress(ValueError):
        text += result.stderr or ""
    return text


def closed_port() -> int:
    """A port with nothing listening on it.

    Bind, read the assigned port, release. Hardcoding a "probably free" port makes the test pass or
    fail depending on what else the developer happens to be running -- which is exactly how this
    test failed the first time it ran here, with the lab target live on 9000.
    """
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


# ------------------------------------------------------------------------------------------------
# version
# ------------------------------------------------------------------------------------------------


def test_version_reports_both_versions() -> None:
    """Engine and plugin API versions move independently (ADR-015), so both are shown."""
    result = runner.invoke(app, ["version"])

    assert result.exit_code == ExitCode.OK
    assert __version__ in result.stdout
    assert PLUGIN_API_VERSION in result.stdout


def test_version_lists_available_adapters() -> None:
    result = runner.invoke(app, ["version"])

    assert "fastapi" in result.stdout


# ------------------------------------------------------------------------------------------------
# plugins
# ------------------------------------------------------------------------------------------------


def test_plugins_lists_a_dropped_in_plugin(cli_root: Path) -> None:
    result = invoke(["plugins"], cli_root)

    assert result.exit_code == ExitCode.OK
    assert "fixture-attack" in result.stdout


def test_plugins_reports_when_none_are_installed(lab_root: Path) -> None:
    (lab_root / "configs" / "ragstrike.yaml").write_text(
        "version: 1\nlogging:\n  console: false\n", encoding="utf-8"
    )

    result = invoke(["plugins"], lab_root)

    assert result.exit_code == ExitCode.OK
    assert "No active plugins" in result.stdout


def test_plugins_shows_rejections(lab_root: Path, make_plugin) -> None:
    """A refused plugin the operator never hears about changes results invisibly."""
    (lab_root / "configs" / "ragstrike.yaml").write_text(
        "version: 1\nlogging:\n  console: false\n", encoding="utf-8"
    )
    make_plugin("future-attack", directory=lab_root / "plugins", api_range=">=99.0")

    result = invoke(["plugins"], lab_root)

    assert "Rejected" in result.stdout
    assert "incompatible" in result.stdout


# ------------------------------------------------------------------------------------------------
# targets
# ------------------------------------------------------------------------------------------------


def test_targets_lists_configuration(cli_root: Path) -> None:
    result = invoke(["targets"], cli_root)

    assert result.exit_code == ExitCode.OK
    assert "lab" in result.stdout
    assert "fastapi" in result.stdout


def test_targets_flags_missing_authorization(lab_root: Path) -> None:
    (lab_root / "configs" / "ragstrike.yaml").write_text(
        "version: 1\nlogging:\n  console: false\n", encoding="utf-8"
    )
    write_targets_yaml(
        lab_root / "configs" / "targets.yaml",
        [{"name": "unsafe", "url": "http://127.0.0.1:9000", "adapter": "fastapi"}],
    )

    result = invoke(["targets"], lab_root)

    assert "cannot be scanned" in result.stdout


def test_targets_reports_none_configured(lab_root: Path) -> None:
    (lab_root / "configs" / "ragstrike.yaml").write_text(
        "version: 1\nlogging:\n  console: false\n", encoding="utf-8"
    )

    result = invoke(["targets"], lab_root)

    assert "No targets configured" in result.stdout


# ------------------------------------------------------------------------------------------------
# scan -- exit codes
# ------------------------------------------------------------------------------------------------


def test_scan_exits_unauthorized_without_an_authorization_record(
    lab_root: Path, make_plugin
) -> None:
    (lab_root / "configs" / "ragstrike.yaml").write_text(
        "version: 1\nlogging:\n  console: false\n", encoding="utf-8"
    )
    write_targets_yaml(
        lab_root / "configs" / "targets.yaml",
        [{"name": "unsafe", "url": "http://127.0.0.1:9000", "adapter": "fastapi"}],
    )
    make_plugin("fixture-attack", directory=lab_root / "plugins")

    result = invoke(["scan"], lab_root)

    assert result.exit_code == ExitCode.UNAUTHORIZED


def test_scan_exits_unreachable_when_the_target_is_down(lab_root: Path, make_plugin) -> None:
    (lab_root / "configs" / "ragstrike.yaml").write_text(
        "version: 1\nlogging:\n  console: false\n", encoding="utf-8"
    )
    write_targets_yaml(
        lab_root / "configs" / "targets.yaml",
        [
            {
                "name": "down",
                "url": f"http://127.0.0.1:{closed_port()}",
                "adapter": "fastapi",
                "authorization": {"authorized_by": "t", "authorization_ref": "R"},
            }
        ],
    )
    make_plugin("fixture-attack", directory=lab_root / "plugins")

    result = invoke(["scan"], lab_root)

    assert result.exit_code == ExitCode.UNREACHABLE


def test_scan_exits_configuration_for_an_unknown_target(cli_root: Path) -> None:
    result = invoke(["scan", "--target", "nope"], cli_root)

    assert result.exit_code == ExitCode.CONFIGURATION


def test_scan_exits_configuration_for_an_unknown_adapter(lab_root: Path, make_plugin) -> None:
    (lab_root / "configs" / "ragstrike.yaml").write_text(
        "version: 1\nlogging:\n  console: false\n", encoding="utf-8"
    )
    write_targets_yaml(
        lab_root / "configs" / "targets.yaml",
        [
            {
                "name": "weird",
                "url": "http://127.0.0.1:9000",
                "adapter": "telepathy",
                "authorization": {"authorized_by": "t", "authorization_ref": "R"},
            }
        ],
    )
    make_plugin("fixture-attack", directory=lab_root / "plugins")

    result = invoke(["scan"], lab_root)

    assert result.exit_code == ExitCode.CONFIGURATION


def test_scan_refuses_a_non_loopback_target_by_default(lab_root: Path, make_plugin) -> None:
    """Two deliberate steps are required to reach anything but this machine (ADR-017)."""
    (lab_root / "configs" / "ragstrike.yaml").write_text(
        "version: 1\nlogging:\n  console: false\n", encoding="utf-8"
    )
    write_targets_yaml(
        lab_root / "configs" / "targets.yaml",
        [
            {
                "name": "remote",
                "url": "http://198.51.100.7:9000",
                "adapter": "fastapi",
                "authorization": {"authorized_by": "t", "authorization_ref": "R"},
            }
        ],
    )
    make_plugin("fixture-attack", directory=lab_root / "plugins")

    result = invoke(["scan"], lab_root)

    assert result.exit_code == ExitCode.CONFIGURATION
    text = output_of(result)
    assert "loopback" in text or "allow_remote_targets" in text


def test_help_lists_every_command() -> None:
    result = runner.invoke(app, ["--help"])

    for command in ("scan", "plugins", "targets", "version"):
        assert command in result.stdout
