"""RAGStrike command line interface.

    ragstrike scan       run the full lifecycle against a target
    ragstrike plugins    what is installed, and what was refused
    ragstrike targets    what is configured, and what is authorized
    ragstrike version    engine and plugin API versions

**This module is the composition root.** It is the only place that knows every concrete class --
which database, which adapter, which registry -- and wires them into the engine. Everything below it
depends on ports. That is what keeps SC3 true: swapping the adapter changes this file and nothing
else.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer

from ragstrike import PLUGIN_API_VERSION, __version__
from ragstrike.analyzers.config import build_engine as build_analyzer
from ragstrike.cli.exit_codes import ExitCode
from ragstrike.cli.output import console as ui
from ragstrike.core.config.loader import REPO_ROOT, load_settings, load_targets, select_target
from ragstrike.core.config.models import Settings
from ragstrike.core.config.profiles import ScanProfile, load_all_profiles, load_profile
from ragstrike.core.errors import (
    AuthorizationError,
    ConfigurationError,
    RAGStrikeError,
    TargetError,
    TargetUnreachableError,
)
from ragstrike.core.orchestrator.scan_engine import ScanEngine
from ragstrike.database.connection import Database
from ragstrike.database.migrations.runner import run_migrations
from ragstrike.database.repositories.finding_repository import FindingRepository
from ragstrike.database.repositories.scan_repository import ScanRepository
from ragstrike.database.repositories.target_repository import TargetRepository
from ragstrike.logging.setup import setup_logging
from ragstrike.models.entities.target import Target
from ragstrike.plugins.registry.plugin_manager import PluginManager
from ragstrike.plugins.registry.plugin_registry import PluginRegistry
from ragstrike.scheduler.scan_scheduler import ScanScheduler
from ragstrike.target_adapters.registry import available as available_adapters
from ragstrike.target_adapters.registry import build_adapter

app = typer.Typer(
    name="ragstrike",
    help="An extensible offensive security evaluation framework for RAG systems.",
    add_completion=False,
    no_args_is_help=True,
)


def _bootstrap(
    config: Path | None, *, quiet: bool = False, profile: ScanProfile | None = None
) -> Settings:
    """Load configuration and start logging. Every command begins here."""
    settings = load_settings(config_file=config, profile=profile)
    setup_logging(
        log_dir=settings.logging.log_dir,
        level=settings.logging.level,
        json_lines=settings.logging.json_lines,
        console=settings.logging.console and not quiet,
    )
    return settings


def _registry(settings: Settings) -> PluginRegistry:
    """Build the registry with the plugins.yaml path threaded in.

    Phase 4 added ``configs/plugins.yaml`` for per-plugin runtime overrides. Threading its path
    through here means the registry can honour ``enabled: false`` and the manager can write back
    to it -- both while keeping the file location out of every callsite.
    """
    plugin_config_path = REPO_ROOT / "configs" / "plugins.yaml"
    return PluginRegistry(
        settings.plugins,
        api_version=PLUGIN_API_VERSION,
        plugin_config_path=plugin_config_path,
    )


def _manager(settings: Settings) -> PluginManager:
    return PluginManager(_registry(settings))


# --------------------------------------------------------------------------------------------
# scan
# --------------------------------------------------------------------------------------------


@app.command()
def scan(
    target_name: Annotated[
        str | None, typer.Option("--target", "-t", help="Target name from targets.yaml.")
    ] = None,
    config: Annotated[
        Path | None, typer.Option("--config", "-c", help="Path to ragstrike.yaml.")
    ] = None,
    targets_file: Annotated[
        Path | None, typer.Option("--targets", help="Path to targets.yaml.")
    ] = None,
    profile_name: Annotated[
        str | None,
        typer.Option(
            "--profile", "-p", help="Scan profile from configs/profiles/ (quick|standard|deep)."
        ),
    ] = None,
    fail_on_findings: Annotated[
        bool,
        typer.Option(
            "--fail-on-findings/--no-fail-on-findings", help="Exit 1 if any plugin FAILs."
        ),
    ] = True,
) -> None:
    """Run a scan.

    The full lifecycle: load configuration, initialise the database, discover plugins, connect to
    the target, execute, store, exit. It works correctly with zero real attack plugins installed --
    that is what makes it an engine rather than a scanner.
    """
    try:
        profile = load_profile(profile_name, root=REPO_ROOT) if profile_name else None
        settings = _bootstrap(config, profile=profile)
        targets = load_targets(targets_file=targets_file)
        target = select_target(targets, target_name)
        code = asyncio.run(
            _run_scan(settings, target, profile=profile, fail_on_findings=fail_on_findings)
        )
    except AuthorizationError as exc:
        ui.failure(exc)
        raise typer.Exit(ExitCode.UNAUTHORIZED) from exc
    except (ConfigurationError, TargetError) as exc:
        ui.failure(exc)
        unreachable = isinstance(exc, TargetUnreachableError)
        raise typer.Exit(ExitCode.UNREACHABLE if unreachable else ExitCode.CONFIGURATION) from exc
    except RAGStrikeError as exc:
        ui.failure(exc)
        raise typer.Exit(ExitCode.SCAN_ERROR) from exc

    raise typer.Exit(code)


async def _run_scan(
    settings: Settings,
    target: Target,
    *,
    profile: ScanProfile | None = None,
    fail_on_findings: bool,
) -> int:
    """Wire everything together and run one scan.

    The composition root proper: this is where ports meet implementations.
    """
    ui.banner(__version__)

    database = Database(settings.storage.database_path)
    await run_migrations(database)

    registry = _registry(settings)
    scheduler = ScanScheduler(max_concurrency=settings.engine.max_concurrency)

    # Without this the scan stores raw plugin results and stops. That is what it did until now:
    # the analyzer and the reporting engine both existed and nothing joined them, so the findings
    # table stayed empty and every report scored 0.0 out of 10.
    analyzer, analyzer_config = build_analyzer(REPO_ROOT / "configs" / "analyzer")
    if analyzer_config.missing:
        ui.console.print(
            f"[yellow]Analyzer configuration incomplete: {', '.join(analyzer_config.missing)}. "
            f"Defaults are in use.[/yellow]"
        )

    engine = ScanEngine(
        settings=settings,
        registry=registry,
        scheduler=scheduler,
        scan_repository=ScanRepository(database),
        target_repository=TargetRepository(database),
        engine_version=__version__,
        analyzer=analyzer,
        finding_repository=FindingRepository(database),
    )

    # The scope check happens inside build_adapter (Phase 6), so it cannot be skipped by a call
    # site that forgets it. Threading the operator's real policy through is what allows a
    # deliberately configured remote target; omitting it would silently fall back to loopback-only.
    adapter = build_adapter(
        target,
        allow_remote=settings.safety.allow_remote_targets,
        allowed_hosts=settings.safety.allowed_hosts,
        retry=settings.engine.retry,
    )

    ui.scan_header(
        target=target.name,
        url=target.url,
        adapter=target.adapter,
        plugins=len(registry.discover().active),
    )

    try:
        outcome = await engine.run(
            target=target, adapter=adapter, profile=profile, on_result=ui.result_line
        )
    finally:
        await adapter.close()

    ui.scan_summary(outcome.session)

    if outcome.plan.missing:
        # Loud, because this is the failure the profile fix was for: a profile asking for a pack
        # nobody built used to produce a narrower scan than the file implied, with no line saying so.
        ui.console.print(
            f"[yellow]The scan profile named {len(outcome.plan.missing)} pack(s) that are not "
            f"installed: {', '.join(outcome.plan.missing)}.[/yellow]"
        )
        ui.console.print(
            "[dim]  Those categories were NOT tested. Coverage above excludes them.[/dim]"
        )

    if outcome.plugin_health.rejected:
        ui.console.print(
            f"[yellow]{len(outcome.plugin_health.rejected)} plugin(s) refused — "
            f"run `ragstrike plugins` for details.[/yellow]"
        )

    if fail_on_findings and outcome.has_failures:
        return ExitCode.FINDINGS
    if outcome.session.plugins_errored:
        return ExitCode.SCAN_ERROR
    return ExitCode.OK


# --------------------------------------------------------------------------------------------
# plugins
# --------------------------------------------------------------------------------------------


# --------------------------------------------------------------------------------------------
# plugins -- Phase 4 sub-command group
#
# ``ragstrike plugins`` (with no subcommand) keeps its Phase 3 behaviour: shows the health table.
# The subcommands add operational surface: info, enable, disable, validate, reload.
#
# Every subcommand goes through the same PluginManager, which is the single place plugin state
# gets mutated -- writes to plugins.yaml happen there and nowhere else.
# --------------------------------------------------------------------------------------------


plugins_app = typer.Typer(
    name="plugins",
    help="Inspect and manage attack plugins.",
    invoke_without_command=True,
    no_args_is_help=False,
)
app.add_typer(plugins_app, name="plugins")


@plugins_app.callback()
def plugins_root(
    ctx: typer.Context,
    config: Annotated[Path | None, typer.Option("--config", "-c")] = None,
) -> None:
    """Show installed plugins when called without a subcommand.

    Discovery is automatic. No plugin is registered anywhere in the engine: drop a directory
    containing ``metadata.yaml`` into ``./plugins/`` and it appears here.
    """
    if ctx.invoked_subcommand is not None:
        return
    _do_list(config)


@plugins_app.command("list")
def plugins_list(
    config: Annotated[Path | None, typer.Option("--config", "-c")] = None,
) -> None:
    """List every installed plugin, active or refused."""
    _do_list(config)


def _do_list(config: Path | None) -> None:
    try:
        settings = _bootstrap(config, quiet=True)
    except RAGStrikeError as exc:
        ui.failure(exc)
        raise typer.Exit(ExitCode.CONFIGURATION) from exc

    health = _registry(settings).discover()
    ui.plugin_table(health)
    ui.console.print(
        f"\n[dim]Searched: {', '.join(str(d) for d in settings.plugins.local_dirs)}[/dim]"
    )
    ui.console.print(f"[dim]Entry points: {settings.plugins.entry_point_group}[/dim]")


@plugins_app.command("info")
def plugins_info(
    slug: Annotated[str, typer.Argument(help="Plugin slug to inspect.")],
    config: Annotated[Path | None, typer.Option("--config", "-c")] = None,
) -> None:
    """Full metadata for one plugin."""
    try:
        settings = _bootstrap(config, quiet=True)
    except RAGStrikeError as exc:
        ui.failure(exc)
        raise typer.Exit(ExitCode.CONFIGURATION) from exc

    info = _manager(settings).info(slug)
    if info is None:
        ui.error_console.print(
            f"\n[bold red]not-found[/bold red]  no plugin named {slug!r}\n"
            f"[yellow]→[/yellow] run `ragstrike plugins list` to see what is installed."
        )
        raise typer.Exit(ExitCode.CONFIGURATION)

    ui.plugin_info(info)


@plugins_app.command("enable")
def plugins_enable(
    slug: Annotated[str, typer.Argument(help="Plugin slug to enable.")],
    config: Annotated[Path | None, typer.Option("--config", "-c")] = None,
) -> None:
    """Enable a plugin. Persists to configs/plugins.yaml."""
    _toggle(slug, config, enable=True)


@plugins_app.command("disable")
def plugins_disable(
    slug: Annotated[str, typer.Argument(help="Plugin slug to disable.")],
    config: Annotated[Path | None, typer.Option("--config", "-c")] = None,
) -> None:
    """Disable a plugin. Persists to configs/plugins.yaml -- no scan will schedule it."""
    _toggle(slug, config, enable=False)


def _toggle(slug: str, config: Path | None, *, enable: bool) -> None:
    try:
        settings = _bootstrap(config, quiet=True)
    except RAGStrikeError as exc:
        ui.failure(exc)
        raise typer.Exit(ExitCode.CONFIGURATION) from exc

    manager = _manager(settings)
    # Force discovery so the operator sees a "no such plugin" diagnostic when they typo.
    known = {p.slug for p in manager.summaries()}
    if slug not in known:
        ui.error_console.print(
            f"\n[bold red]not-found[/bold red]  no plugin named {slug!r}\n"
            f"[yellow]→[/yellow] known slugs: {', '.join(sorted(known)) or '(none)'}"
        )
        raise typer.Exit(ExitCode.CONFIGURATION)

    if enable:
        manager.enable(slug)
        ui.console.print(f"[green]enabled[/green] [bold]{slug}[/bold]")
    else:
        manager.disable(slug)
        ui.console.print(f"[yellow]disabled[/yellow] [bold]{slug}[/bold]")


@plugins_app.command("validate")
def plugins_validate(
    slug: Annotated[
        str | None, typer.Argument(help="Plugin slug. Omit to validate everything.")
    ] = None,
    config: Annotated[Path | None, typer.Option("--config", "-c")] = None,
) -> None:
    """Run every validation rule against one plugin or all of them.

    Combines framework-level rules (folder shape, manifest fields, API compatibility, class
    contract) with each plugin's own :meth:`validate`.
    """
    try:
        settings = _bootstrap(config, quiet=True)
    except RAGStrikeError as exc:
        ui.failure(exc)
        raise typer.Exit(ExitCode.CONFIGURATION) from exc

    reports = _manager(settings).validate(slug)
    if not reports:
        ui.console.print(
            f"[yellow]No plugin named {slug!r}[/yellow]"
            if slug
            else "[yellow]No plugins found.[/yellow]"
        )
        return

    any_failed = False
    for reported_slug, report in reports:
        ui.validation_table(reported_slug, report)
        if not report.valid:
            any_failed = True

    if any_failed:
        raise typer.Exit(ExitCode.CONFIGURATION)


@plugins_app.command("reload")
def plugins_reload(
    config: Annotated[Path | None, typer.Option("--config", "-c")] = None,
) -> None:
    """Force re-discovery.

    Python's import system caches modules, and blowing that cache away for third-party code is a
    good way to end up with two versions of a class in memory. This refreshes the state the
    registry can safely refresh -- runtime config, capability filtering, health -- and leaves
    cached instances alone.
    """
    try:
        settings = _bootstrap(config, quiet=True)
    except RAGStrikeError as exc:
        ui.failure(exc)
        raise typer.Exit(ExitCode.CONFIGURATION) from exc

    health = _manager(settings).reload()
    ui.plugin_table(health)
    ui.console.print(
        f"\n[dim]Reloaded: {len(health.active)} active, {len(health.rejected)} refused.[/dim]"
    )


# --------------------------------------------------------------------------------------------
# targets
# --------------------------------------------------------------------------------------------


@app.command()
def targets(
    config: Annotated[Path | None, typer.Option("--config", "-c")] = None,
    targets_file: Annotated[Path | None, typer.Option("--targets")] = None,
    verify: Annotated[
        bool, typer.Option("--verify", help="Probe each target and report reachability.")
    ] = False,
) -> None:
    """List configured targets, and optionally probe them."""
    try:
        settings = _bootstrap(config, quiet=True)
        configured = load_targets(targets_file=targets_file)
    except RAGStrikeError as exc:
        ui.failure(exc)
        raise typer.Exit(ExitCode.CONFIGURATION) from exc

    if not configured:
        ui.console.print("[yellow]No targets configured.[/yellow]")
        ui.console.print("[dim]Add one to configs/targets.yaml.[/dim]")
        return

    ui.target_table(configured)
    ui.console.print(f"\n[dim]Adapters available: {', '.join(available_adapters())}[/dim]")

    if verify:
        asyncio.run(_verify_targets(configured, settings))


async def _verify_targets(configured: Sequence[Target], settings: Settings) -> None:
    """Probe each configured target.

    Takes ``settings`` because probing is network egress like any other: before Phase 6 this
    function built adapters without the scope policy and health-checked whatever was in
    ``targets.yaml``, which made ``--verify`` a way to reach a non-loopback host that ``scan``
    would have refused. The guard now lives in ``build_adapter``, and the out-of-scope target is
    reported in the same line-per-target style as an unreachable one rather than aborting the
    whole listing -- one bad entry should not hide the rest.
    """
    ui.console.print("\n[bold]Reachability[/bold]")
    for target in configured:
        try:
            adapter = build_adapter(
                target,
                allow_remote=settings.safety.allow_remote_targets,
                allowed_hosts=settings.safety.allowed_hosts,
            )
        except RAGStrikeError as exc:
            ui.console.print(f"  [yellow]?[/yellow] {target.name}: {exc.message}")
            continue
        try:
            result = await adapter.health_check()
        finally:
            await adapter.close()

        if result.reachable:
            ui.console.print(
                f"  [green]OK[/green] {target.name}  [dim]{result.latency_ms}ms "
                f"{result.detail}[/dim]"
            )
        else:
            ui.console.print(f"  [red]--[/red] {target.name}  [dim]{result.detail}[/dim]")


# --------------------------------------------------------------------------------------------
# profiles
# --------------------------------------------------------------------------------------------


@app.command()
def profiles() -> None:
    """List the scan profiles in ``configs/profiles/``.

    Profiles select depth: which packs run, which payload tiers, and how many attempts each payload
    gets. Pass one to a scan with ``--profile``.
    """
    found = load_all_profiles(root=REPO_ROOT)
    if not found:
        ui.console.print("[yellow]No scan profiles found in configs/profiles/.[/yellow]")
        return
    ui.profile_table(found)


@app.command()
def version() -> None:
    """Show engine and plugin API versions.

    The plugin API version moves independently of the application version (ADR-015). Packs declare
    compatibility against the former, so an application patch release does not signal a break to
    every third-party author.
    """
    ui.banner(__version__)
    ui.console.print(f"  engine       [bold]{__version__}[/bold]")
    ui.console.print(f"  plugin API   [bold]{PLUGIN_API_VERSION}[/bold]")
    ui.console.print(f"  adapters     {', '.join(available_adapters())}")
    ui.console.print(f"  repo root    [dim]{REPO_ROOT}[/dim]")


if __name__ == "__main__":  # pragma: no cover
    app()
