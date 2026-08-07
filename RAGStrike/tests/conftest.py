"""Shared fixtures.

Two rules shape this suite:

**No test touches a network.** ``FakeTarget`` implements the ``TargetAdapter`` port with scripted
responses. A suite that needs a running target is a suite that gets skipped.

**Every test gets its own everything.** A temp repo root, a temp database, a temp plugin directory.
Shared state produces failures that only appear in a particular run order.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import textwrap
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "src") not in sys.path:  # pragma: no cover - editable installs cover this
    sys.path.insert(0, str(REPO_ROOT / "src"))

from ragstrike.core.config.loader import load_settings  # noqa: E402
from ragstrike.core.config.models import Settings  # noqa: E402
from ragstrike.core.contracts.target_adapter import (  # noqa: E402
    HealthResult,
    TargetDescriptor,
    TargetRequest,
    TargetResponse,
)
from ragstrike.database.connection import Database  # noqa: E402
from ragstrike.database.migrations.runner import run_migrations  # noqa: E402
from ragstrike.models.entities.target import Authorization, Target  # noqa: E402
from ragstrike.models.values.enums import Capability  # noqa: E402

# ------------------------------------------------------------------------------------------------
# Test doubles
# ------------------------------------------------------------------------------------------------


class FakeTarget:
    """A scripted ``TargetAdapter``.

    Records every prompt it received, which is what lets a test assert a payload actually reached
    the target rather than inferring it from a downstream effect.
    """

    def __init__(
        self,
        *,
        reply: str = "I am a scripted target.",
        reachable: bool = True,
        capabilities: tuple[Capability, ...] = (Capability.CHAT,),
        raises: Exception | None = None,
    ) -> None:
        self.reply = reply
        self.reachable = reachable
        self.capabilities = capabilities
        self.raises = raises
        self.prompts: list[str] = []
        self.closed = False

    def describe(self) -> TargetDescriptor:
        return TargetDescriptor(
            adapter="fake", version="1.0.0", url="http://fake", capabilities=self.capabilities
        )

    async def health_check(self) -> HealthResult:
        return HealthResult(
            reachable=self.reachable, latency_ms=1, detail="" if self.reachable else "down"
        )

    async def chat(self, request: TargetRequest) -> TargetResponse:
        self.prompts.append(request.prompt)
        if self.raises is not None:
            raise self.raises
        return TargetResponse(text=self.reply, latency_ms=1, session_id="fake-session")

    async def close(self) -> None:
        self.closed = True


# ------------------------------------------------------------------------------------------------
# Plugin fixtures
# ------------------------------------------------------------------------------------------------

_FIXTURE_PLUGIN = """
from ragstrike.core.contracts.target_adapter import TargetRequest
from ragstrike.models.values.enums import Capability, PluginOutcome, Severity
from ragstrike.plugins.base.attack import (
    Analysis, AttackMetadata, BaseAttack, ExecutionRecord, Payload, Recommendation,
)


class {class_name}(BaseAttack):
    def metadata(self):
        return AttackMetadata(
            slug="{slug}", name="{slug}", version="{version}", category="fixture",
            severity=Severity.INFO, requires_capabilities=({capability},),
        )

    def payloads(self):
        return [Payload(id="p1", content="ping")]

    async def execute(self, target, payloads):
        records = []
        for payload in payloads:
            response = await target.chat(TargetRequest(prompt=payload.content))
            records.append(ExecutionRecord(payload.id, payload.content, response))
        return records

    def analyze(self, records):
        return Analysis(outcome=PluginOutcome.{outcome}, summary="fixture")

    def recommendation(self, analysis):
        return Recommendation(title="none", remediation="none")
"""

_FIXTURE_MANIFEST = """
schema_version: 1
plugin:
  slug: {slug}
  name: {slug}
  version: "{version}"
  category: fixture
  entry_point: "attack:{class_name}"
compatibility:
  ragstrike_api: "{api_range}"
permissions:
  network_egress: {network}
  filesystem_write: false
"""


@pytest.fixture
def make_plugin(tmp_path: Path):
    """Build a plugin directory on disk.

    Writing a real directory rather than mocking discovery is the point: the whole claim of the
    plugin system is "drop a folder in and it is found", and only a real folder tests that.
    """

    def _make(
        slug: str = "fixture-attack",
        *,
        directory: Path | None = None,
        version: str = "1.0.0",
        api_range: str = ">=1.0,<2.0",
        outcome: str = "PASS",
        capability: str = "Capability.CHAT",
        network: bool = False,
        broken_manifest: bool = False,
        broken_code: bool = False,
    ) -> Path:
        root = directory or (tmp_path / "plugins")
        plugin_dir = root / slug.replace("-", "_")
        plugin_dir.mkdir(parents=True, exist_ok=True)
        class_name = "".join(part.capitalize() for part in slug.replace("-", "_").split("_"))

        if broken_manifest:
            (plugin_dir / "pack.yaml").write_text("plugin: [not, a, mapping\n", encoding="utf-8")
        else:
            (plugin_dir / "pack.yaml").write_text(
                _FIXTURE_MANIFEST.format(
                    slug=slug,
                    version=version,
                    class_name=class_name,
                    api_range=api_range,
                    network=str(network).lower(),
                ),
                encoding="utf-8",
            )

        code = (
            "raise RuntimeError('this plugin is broken')\n"
            if broken_code
            else textwrap.dedent(
                _FIXTURE_PLUGIN.format(
                    class_name=class_name,
                    slug=slug,
                    version=version,
                    outcome=outcome,
                    capability=capability,
                )
            )
        )
        (plugin_dir / "attack.py").write_text(code, encoding="utf-8")
        return root

    return _make


# ------------------------------------------------------------------------------------------------
# Configuration and storage
# ------------------------------------------------------------------------------------------------


@pytest.fixture
def lab_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A temp repository root with its own configs directory.

    ``RAGSTRIKE_*`` variables from the developer's shell are cleared, or they would leak into every
    test and make failures depend on who ran them.
    """
    for key in list(os.environ):
        if key.startswith("RAGSTRIKE_"):
            monkeypatch.delenv(key, raising=False)
    (tmp_path / "configs").mkdir()
    return tmp_path


@pytest.fixture
def settings(lab_root: Path) -> Settings:
    (lab_root / "configs" / "ragstrike.yaml").write_text(
        "version: 1\nlogging:\n  console: false\n", encoding="utf-8"
    )
    return load_settings(root=lab_root)


@pytest.fixture
def authorized_target() -> Target:
    return Target(
        id=Target.new_id(),
        name="fixture-target",
        adapter="fastapi",
        url="http://127.0.0.1:9000",
        authorization=Authorization(
            authorized_by="tester", authorization_ref="TEST-1", scope="local fixture"
        ),
    )


@pytest.fixture
def unauthorized_target() -> Target:
    return Target(
        id=Target.new_id(),
        name="no-auth-target",
        adapter="fastapi",
        url="http://127.0.0.1:9000",
    )


async def make_database(settings: Settings) -> Database:
    """Build a migrated database. A helper rather than a fixture: async fixtures that return a
    value need extra plumbing, and every caller here is already inside an async test."""
    database = Database(settings.storage.database_path)
    await run_migrations(database)
    return database


def write_targets_yaml(path: Path, entries: list[dict[str, Any]]) -> Path:
    import yaml

    path.write_text(yaml.safe_dump({"version": 1, "targets": entries}), encoding="utf-8")
    return path
