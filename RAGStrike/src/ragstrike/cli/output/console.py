"""Rich rendering for the CLI.

Isolated here so that no command calls ``print`` directly. Presentation lives in one place, and the
JSON output mode planned for CI cannot be corrupted by a stray write.

Outcome colouring follows the defender's frame throughout: **PASS is green** because the target
resisted, **FAIL is red** because it is vulnerable. Getting that backwards in a security tool is
worse than having no colour at all.
"""

from __future__ import annotations

from collections.abc import Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ragstrike.core.config.profiles import ScanProfile
from ragstrike.core.errors import RAGStrikeError
from ragstrike.models.entities.scan import PluginResult, ScanSession
from ragstrike.models.entities.target import Target
from ragstrike.models.values.enums import PluginOutcome
from ragstrike.plugins.base.reports import ValidationReport
from ragstrike.plugins.registry.plugin_manager import PluginInfo
from ragstrike.plugins.registry.plugin_registry import PluginHealth

console = Console()
error_console = Console(stderr=True)

#: Below this fraction, a result is stamped "partial coverage" -- a grade derived from a third of
#: the plugin set is not the same statement as one derived from all of it.
_PARTIAL_COVERAGE = 0.6

# INCONCLUSIVE (Phase 6) is deliberately cyan rather than a shade of green or red: it is not a
# weaker PASS and not a softer FAIL, and colouring it as either would smuggle a verdict into a
# result that does not have one. Yellow already means ERROR -- "the tooling broke" -- which is a
# different message from "the target answered and the answer settles nothing".
_OUTCOME_STYLE = {
    PluginOutcome.PASS: "bold green",
    PluginOutcome.FAIL: "bold red",
    PluginOutcome.INCONCLUSIVE: "bold cyan",
    PluginOutcome.ERROR: "bold yellow",
    PluginOutcome.SKIPPED: "dim",
}

_OUTCOME_LABEL = {
    PluginOutcome.PASS: "PASS",
    PluginOutcome.FAIL: "FAIL",
    PluginOutcome.INCONCLUSIVE: "INCONC",
    PluginOutcome.ERROR: "ERROR",
    PluginOutcome.SKIPPED: "SKIP",
}


def banner(version: str) -> None:
    console.print(
        Panel(
            Text.from_markup(
                "[bold]RAGStrike[/bold]  [dim]offensive security evaluation for RAG systems[/dim]\n"
                f"[dim]engine {version}[/dim]"
            ),
            border_style="cyan",
            padding=(0, 2),
        )
    )


def scan_header(*, target: str, url: str, adapter: str, plugins: int) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()
    table.add_row("Target", f"[bold]{target}[/bold]")
    table.add_row("URL", url)
    table.add_row("Adapter", adapter)
    table.add_row("Plugins", str(plugins))
    console.print(table)
    console.print()


def result_line(result: PluginResult) -> None:
    """One line per plugin, printed as it completes."""
    style = _OUTCOME_STYLE[result.outcome]
    label = _OUTCOME_LABEL[result.outcome]
    console.print(
        f"  [{style}]{label:<5}[/{style}]  "
        f"[bold]{result.plugin_slug}[/bold]  "
        f"[dim]{result.elapsed_ms}ms[/dim]  {result.summary}"
    )


def scan_summary(session: ScanSession) -> None:
    """The closing panel.

    Coverage is shown next to the counts, always. A scan that skipped most of its plugins and one
    that ran them all both say "0 failed" otherwise, and those are very different statements.
    """
    table = Table.grid(padding=(0, 3))
    table.add_column(style="dim")
    table.add_column(justify="right")

    table.add_row("Executed", str(session.plugins_executed))
    table.add_row("[green]Passed[/green]", str(session.plugins_passed))
    table.add_row("[red]Failed[/red]", str(session.plugins_failed))
    table.add_row("[yellow]Errored[/yellow]", str(session.plugins_errored))
    table.add_row("Skipped", str(session.plugins_skipped))
    table.add_row("Coverage", f"{session.coverage * 100:.0f}%")
    table.add_row("Duration", f"{session.elapsed_ms}ms")

    verdict = (
        "[bold red]VULNERABILITIES FOUND[/bold red]"
        if session.plugins_failed
        else "[bold green]NO FAILURES[/bold green]"
    )
    if session.coverage < _PARTIAL_COVERAGE and session.plugins_total:
        verdict += "  [yellow](partial coverage)[/yellow]"

    console.print()
    console.print(
        Panel(table, title=verdict, border_style="red" if session.plugins_failed else "green")
    )
    console.print(f"[dim]scan {session.id}[/dim]")


def plugin_table(health: PluginHealth) -> None:
    if health.active:
        table = Table(title="Active plugins", header_style="bold cyan", expand=False)
        table.add_column("Slug")
        table.add_column("Version")
        table.add_column("Category")
        table.add_column("Severity")
        table.add_column("Requires")
        for plugin in health.active:
            meta = plugin.metadata()
            table.add_row(
                plugin.slug,
                plugin.version,
                meta.category,
                meta.severity.value,
                ", ".join(c.value for c in meta.requires_capabilities),
            )
        console.print(table)
    else:
        console.print("[yellow]No active plugins.[/yellow]")
        console.print("[dim]Drop a plugin directory into ./plugins/ and re-run.[/dim]")

    if health.rejected:
        # Never silent. A refused plugin that nobody hears about changes results invisibly.
        table = Table(title="Rejected plugins", header_style="bold yellow", expand=False)
        table.add_column("Slug")
        table.add_column("Reason")
        table.add_column("Detail")
        for rejected in health.rejected:
            table.add_row(rejected.slug, rejected.reason, rejected.detail)
        console.print(table)


def profile_table(profiles: Sequence[ScanProfile]) -> None:
    """The available scan depths.

    ``packs`` shows "all" for an empty selection rather than "0". A profile that selects everything
    and one that selects nothing are opposite facts, and rendering both as a number invites the
    reader to guess which one they are looking at.
    """
    table = Table(title="Scan profiles", header_style="bold cyan", expand=False)
    table.add_column("Profile")
    table.add_column("Packs")
    table.add_column("Tiers")
    table.add_column("Attempts", justify="right")
    table.add_column("Timeout", justify="right")
    table.add_column("Description")

    for profile in profiles:
        timeout = profile.engine.scan_timeout_s
        table.add_row(
            profile.id,
            str(len(profile.packs)) if profile.packs else "all",
            ", ".join(profile.payload_tiers),
            str(profile.attempts),
            f"{timeout}s" if timeout else "-",
            profile.description,
        )
    console.print(table)


def target_table(targets: Sequence[Target]) -> None:
    table = Table(title="Configured targets", header_style="bold cyan", expand=False)
    table.add_column("Name")
    table.add_column("Adapter")
    table.add_column("URL")
    table.add_column("Enabled")
    table.add_column("Authorized")

    for target in targets:
        table.add_row(
            target.name,
            target.adapter,
            target.url,
            "[green]yes[/green]" if target.enabled else "[dim]no[/dim]",
            "[green]yes[/green]" if target.is_authorized else "[red]NO[/red]",
        )
    console.print(table)

    if any(not t.is_authorized for t in targets):
        console.print(
            "\n[yellow]Targets without an authorization record cannot be scanned.[/yellow]\n"
            "[dim]Add authorized_by and authorization_ref to the target in "
            "configs/targets.yaml.[/dim]"
        )


def plugin_info(info: PluginInfo) -> None:
    """Detailed view of one plugin.

    Rendered as a two-column table so an operator can scan for a field without hunting through
    prose. The permissions row is highlighted red when either is set, so an operator can never
    miss that a plugin has been granted elevated access.
    """
    summary = info.summary
    table = Table.grid(padding=(0, 2))
    table.add_column(style="dim")
    table.add_column()

    table.add_row("Slug", f"[bold]{summary.slug}[/bold]")
    table.add_row("Name", summary.name)
    table.add_row("Version", summary.version)
    table.add_row("Category", summary.category)
    table.add_row("Severity", summary.severity)
    table.add_row("Author", info.author or "-")
    table.add_row("License", info.license or "-")
    table.add_row("Target type", info.required_target_type)
    table.add_row("Requires capabilities", ", ".join(info.requires_capabilities) or "-")
    table.add_row("Requires API", info.requires_api)
    table.add_row("Min framework", info.min_framework_version)
    table.add_row("OWASP mapping", ", ".join(info.owasp_mapping) or "-")
    table.add_row("Tags", ", ".join(info.tags) or "-")
    table.add_row("References", "\n".join(info.references) or "-")

    perms = ", ".join(name for name, on in info.permissions.items() if on) or "none"
    perms_style = "red" if perms != "none" else "green"
    table.add_row("Permissions", f"[{perms_style}]{perms}[/{perms_style}]")

    table.add_row("Manifest", f"[dim]{info.manifest_path}[/dim]")
    table.add_row("Source", f"[dim]{summary.source}[/dim]")

    console.print(Panel(table, title=f"[bold]{summary.name}[/bold]", border_style="cyan"))

    if info.description:
        console.print()
        console.print(f"[dim]{info.description}[/dim]")

    if info.options:
        console.print()
        console.print("[bold]Options[/bold]")
        for key, value in info.options.items():
            console.print(f"  [dim]{key}[/dim]  {value}")


def validation_table(slug: str, report: ValidationReport) -> None:
    """Render one plugin's validation report.

    Every rule, passed or failed, appears in the table. The Phase 4 promise is "the framework
    rejects malformed plugins with a reason" -- and "with a reason" means the operator can see
    which rule tripped, not just that something did.
    """
    header = f"[bold green]{slug}[/bold green]" if report.valid else f"[bold red]{slug}[/bold red]"
    table = Table(title=header, header_style="bold cyan", expand=False)
    table.add_column("Rule")
    table.add_column("Result")
    table.add_column("Detail")

    for check in report.checks:
        status = "[green]PASS[/green]" if check.passed else "[red]FAIL[/red]"
        table.add_row(check.rule, status, check.detail or "-")

    console.print(table)


def failure(error: RAGStrikeError) -> None:
    """Render an error as a diagnosis, not a traceback."""
    error_console.print(f"\n[bold red]{error.code}[/bold red]  {error.message}")
    if error.hint:
        error_console.print(f"[yellow]→[/yellow] {error.hint}")
    error_console.print()
