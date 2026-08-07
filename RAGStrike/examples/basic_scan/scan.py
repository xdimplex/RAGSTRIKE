"""Scan one target from Python.

Run:  python examples/basic_scan/scan.py

This is the same ``ScanEngine`` the CLI drives -- there is no private path and no shortcut. If this
script works, an integration into your own tooling works the same way.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from ragstrike import PLUGIN_API_VERSION, __version__  # noqa: E402
from ragstrike.core.config.loader import (  # noqa: E402
    REPO_ROOT,
    load_settings,
    load_targets,
    select_target,
)
from ragstrike.core.orchestrator.scan_engine import ScanEngine  # noqa: E402
from ragstrike.database.connection import Database  # noqa: E402
from ragstrike.database.migrations.runner import run_migrations  # noqa: E402
from ragstrike.database.repositories.scan_repository import ScanRepository  # noqa: E402
from ragstrike.database.repositories.target_repository import TargetRepository  # noqa: E402
from ragstrike.plugins.registry.plugin_registry import PluginRegistry  # noqa: E402
from ragstrike.scheduler.scan_scheduler import ScanScheduler  # noqa: E402
from ragstrike.target_adapters.registry import build_adapter  # noqa: E402

TARGET = "vulnerable-rag"


async def main() -> int:
    print(f"RAGStrike {__version__} (plugin API {PLUGIN_API_VERSION})")

    settings = load_settings()
    target = select_target(load_targets(), TARGET)

    database = Database(settings.storage.database_path)
    await run_migrations(database)

    registry = PluginRegistry(
        settings.plugins,
        api_version=PLUGIN_API_VERSION,
        plugin_config_path=REPO_ROOT / "configs" / "plugins.yaml",
    )
    health = registry.discover()
    print(f"{len(health.active)} plugin(s) active, {len(health.rejected)} refused")

    engine = ScanEngine(
        settings=settings,
        registry=registry,
        scheduler=ScanScheduler(max_concurrency=settings.engine.max_concurrency),
        scan_repository=ScanRepository(database),
        target_repository=TargetRepository(database),
        engine_version=__version__,
    )

    # The scope check lives inside build_adapter so no call site can skip it. Threading the real
    # policy through is what allows a deliberately configured remote target; omitting it would
    # silently fall back to loopback-only.
    adapter = build_adapter(
        target,
        allow_remote=settings.safety.allow_remote_targets,
        allowed_hosts=settings.safety.allowed_hosts,
    )

    try:
        outcome = await engine.run(target=target, adapter=adapter)
    finally:
        await adapter.close()

    print(f"\nscan {outcome.session.id}")
    for result in outcome.results:
        print(f"  {result.outcome.value:<14} {result.plugin_slug:<24} {result.summary[:60]}")

    return 1 if outcome.has_failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
