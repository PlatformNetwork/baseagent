"""Main CLI entry point for SuperAgent."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from src import __version__
from src.config.loader import find_config_file, load_config
from src.config.models import OutputMode, Provider
from src.core.agent import Agent
from src.output.processor import OutputProcessor

app = typer.Typer(
    name="superagent",
    help="Autonomous coding agent inspired by OpenAI Codex CLI",
    add_completion=False,
)

console = Console(stderr=True)


def version_callback(value: bool):
    if value:
        console.print(f"SuperAgent v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
):
    """SuperAgent - Autonomous coding assistant."""
    pass


@app.command("exec")
def exec_command(
    prompt: str = typer.Argument(..., help="The task/prompt for the agent"),
    # Model/Provider options
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
    provider: Optional[Provider] = typer.Option(None, "--provider", "-p", help="LLM provider"),
    # Config options
    config_file: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to config file",
    ),
    # Output options
    json_mode: bool = typer.Option(False, "--json", help="Output in JSONL format"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    # Execution options
    workdir: Optional[Path] = typer.Option(None, "--workdir", "-w", help="Working directory"),
    max_iterations: Optional[int] = typer.Option(None, help="Maximum iterations"),
    # Danger mode (compatibility with Codex CLI)
    dangerously_bypass_approvals: bool = typer.Option(
        False,
        "--dangerously-bypass-approvals-and-sandbox",
        help="Run without sandbox/approvals (default behavior in SuperAgent)",
    ),
):
    """Execute a task with the agent."""

    # Load configuration
    config_path = config_file or find_config_file()

    overrides = {}
    if model:
        overrides["model"] = model
    if provider:
        overrides["provider"] = provider
    if json_mode:
        overrides["output.mode"] = OutputMode.JSON
    if max_iterations:
        overrides["max_iterations"] = max_iterations
    if workdir:
        overrides["paths.cwd"] = str(workdir)

    try:
        config = load_config(config_path, overrides)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1)

    # Setup working directory
    cwd = Path(config.paths.cwd or os.getcwd()).resolve()
    if not cwd.exists():
        console.print(f"[red]Working directory does not exist: {cwd}[/red]")
        raise typer.Exit(1)

    # Initialize output processor
    output = OutputProcessor(config)

    # Run agent
    try:
        agent = Agent(config=config, cwd=cwd, output_processor=output)

        # In JSON mode, we don't print "Starting..." messages to stdout
        if not json_mode:
            console.print(f"[bold blue]SuperAgent v{__version__}[/bold blue]")
            console.print(f"Model: [cyan]{config.model}[/cyan] ({config.provider})")
            console.print(f"Working directory: [cyan]{cwd}[/cyan]")
            console.print()

        final_message = agent.run(prompt)

        # In human mode, print the final message clearly
        if not json_mode and final_message:
            console.print()
            console.print("[bold green]Final Result:[/bold green]")
            output.print_final(final_message)

    except Exception:
        if verbose:
            console.print_exception()
        else:
            # Error is already emitted by agent via output processor
            pass
        raise typer.Exit(1)


@app.command("config")
def show_config(
    config_file: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config file"),
):
    """Show current configuration."""
    path = config_file or find_config_file()
    if path:
        console.print(f"Loading config from: {path}")
        config = load_config(path)
    else:
        console.print("No config file found, using defaults")
        config = load_config()

    console.print(config.model_dump_json(indent=2))


if __name__ == "__main__":
    app()
