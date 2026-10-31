"""DriftCheck CLI - main entry point."""

from __future__ import annotations

import typer
from rich.console import Console

from driftcheck import __version__

app = typer.Typer(
    name="driftcheck",
    help="Automated Documentation Drift Detection",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"driftcheck {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """DriftCheck - The code moved. The docs didn't. DriftCheck notices before your users do."""


# Placeholder subcommands - will be implemented in later phases


@app.command()
def check(
    base: str = typer.Option("HEAD~1", "--base", help="Base commit/ref"),
    head: str = typer.Option("HEAD", "--head", help="Head commit/ref"),
    diff: str | None = typer.Option(None, "--diff", help="Path to a .diff file"),
    repo: str = typer.Option(".", "--repo", help="Repository path"),
    llm: str = typer.Option("none", "--llm", help="LLM mode: none|local|full"),
    format: str = typer.Option("console", "--format", help="Output format"),
    out: str | None = typer.Option(None, "--out", help="Output directory"),
    fix: bool = typer.Option(False, "--fix", help="Auto-fix documentation"),
    fail_on: str = typer.Option("high", "--fail-on", help="Fail on severity"),
    config: str | None = typer.Option(None, "--config", help="Config file path"),
    debug: bool = typer.Option(False, "--debug", help="Debug output"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Disable LLM cache"),
) -> None:
    """Check for documentation drift between two commits."""
    console.print("[yellow]Not implemented yet[/yellow]")
    raise typer.Exit(code=2)


@app.command()
def replay(
    commit: str = typer.Argument(..., help="Commit to replay"),
    repo: str = typer.Option(".", "--repo", help="Repository path"),
    llm: str = typer.Option("none", "--llm", help="LLM mode: none|local|full"),
    format: str = typer.Option("console", "--format", help="Output format"),
) -> None:
    """Replay drift check at a specific commit."""
    console.print("[yellow]Not implemented yet[/yellow]")
    raise typer.Exit(code=2)


@app.command()
def mine(
    repo: str = typer.Option(".", "--repo", help="Repository path"),
    since: str | None = typer.Option(None, "--since", help="Only mine since date"),
    window: int = typer.Option(30, "--window", help="Lookback window in commits"),
    out: str | None = typer.Option(None, "--out", help="Output JSONL file"),
) -> None:
    """Mine labelled drift cases from git history."""
    console.print("[yellow]Not implemented yet[/yellow]")
    raise typer.Exit(code=2)


@app.command()
def eval(
    dataset: str = typer.Argument(..., help="Dataset JSONL file or directory"),
    split: str = typer.Option("test", "--split", help="Split: dev|test"),
    modes: str = typer.Option("none", "--modes", help="Comma-separated modes"),
    out: str | None = typer.Option(None, "--out", help="Output directory"),
) -> None:
    """Evaluate drift detection on a labelled dataset."""
    console.print("[yellow]Not implemented yet[/yellow]")
    raise typer.Exit(code=2)


@app.command()
def hook(
    action: str = typer.Argument(..., help="Action: install|uninstall|run"),
) -> None:
    """Manage git pre-push hook."""
    console.print("[yellow]Not implemented yet[/yellow]")
    raise typer.Exit(code=2)


@app.command()
def ignore(
    fingerprint: str = typer.Argument(..., help="Finding fingerprint or ID"),
    reason: str = typer.Option("", "--reason", help="Dismissal reason"),
) -> None:
    """Dismiss a finding by adding to .driftignore."""
    console.print("[yellow]Not implemented yet[/yellow]")
    raise typer.Exit(code=2)


@app.command()
def github(
    llm: str = typer.Option("none", "--llm", help="LLM mode: none|local|full"),
    fail_on: str = typer.Option("high", "--fail-on", help="Fail on severity"),
    check_name: str = typer.Option("DriftCheck", "--check-name", help="Check run name"),
    out: str | None = typer.Option(None, "--out", help="Output directory"),
) -> None:
    """Run as GitHub Action."""
    console.print("[yellow]Not implemented yet[/yellow]")
    raise typer.Exit(code=2)


@app.command()
def doctor() -> None:
    """Check environment and dependencies."""
    console.print("[yellow]Not implemented yet[/yellow]")
    raise typer.Exit(code=2)
