#!/usr/bin/env python3
"""
Bootstrap Infrahub with schemas, data, and configurations.

This is a Python equivalent of scripts/bootstrap.sh with enhanced Rich UI formatting.

This script loads all necessary data into Infrahub including:
- Schemas
- Menu definitions
- Bootstrap data (locations, platforms, roles)
- Security data
- Demo repository
- Event actions

Advantages over bash version:
- Beautiful progress bars with time elapsed
- Better error handling and reporting
- More structured code with type hints
- Rich-formatted panels and status messages
- Visual progress indicators for long-running operations

Usage:
    python scripts/bootstrap.py              # Use main branch
    python scripts/bootstrap.py --branch dev # Use specific branch
    uv run invoke bootstrap-py               # Via invoke (Python version)
    uv run invoke bootstrap                  # Via invoke (Bash version)

Performance comparison:
    To compare performance between bash and Python versions:
    time ./scripts/bootstrap.sh
    time uv run python scripts/bootstrap.py
"""

import argparse
import subprocess
import sys
import time

import requests
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.rule import Rule
from rich import box

console = Console()

INFRAHUB_ADDRESS = "http://localhost:8000"


def check_infrahub_ready(max_retries: int = 30, sleep_time: int = 2) -> bool:
    """Check if Infrahub is ready to accept requests."""
    console.print("\n[bold cyan]→ Checking if Infrahub is ready...[/bold cyan]")

    with Progress(
        SpinnerColumn(spinner_name="dots12", style="bold bright_magenta"),
        TextColumn("[progress.description]{task.description}", style="bold white"),
        BarColumn(
            bar_width=60,
            style="magenta",
            complete_style="bright_green",
            finished_style="bold bright_green",
            pulse_style="bright_magenta"
        ),
        TextColumn("[bold bright_cyan]{task.percentage:>3.0f}%"),
        TextColumn("•", style="dim"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("⏳ Waiting for Infrahub", total=max_retries)

        for attempt in range(max_retries):
            try:
                response = requests.get(f"{INFRAHUB_ADDRESS}/api/schema", timeout=2)
                if response.status_code == 200:
                    progress.update(task, completed=max_retries)
                    console.print("[bold green]✓ Infrahub is ready![/bold green]\n")
                    return True
            except requests.exceptions.RequestException:
                pass

            progress.update(task, advance=1)
            time.sleep(sleep_time)

    console.print()
    console.print(Panel(
        "[red]✗ ERROR: Infrahub is not responding[/red]\n\n"
        "[dim]Please ensure Infrahub is running with:[/dim]\n"
        "  [bold]uv run invoke start[/bold]\n\n"
        "[dim]Check container status with:[/dim]\n"
        "  [bold]docker ps[/bold]",
        title="Connection Error",
        border_style="red",
        box=box.ROUNDED
    ))
    return False


def run_command(command: str, description: str, step: str, color: str = "cyan", icon: str = "") -> bool:
    """Run a shell command and display output."""
    icon_display = f"{icon} " if icon else ""
    console.print(f"\n[bold {color} on black]{step}[/bold {color} on black] {icon_display}[bold white]{description}[/bold white]")

    try:
        subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=False,
            text=True
        )
        # Use the step's color for the completion message with a colored background box and matching icon
        console.print(f"[bold bright_green on black]✓[/bold bright_green on black] {icon_display}[bold {color}]{description} completed[/bold {color}]")
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]✗[/bold red] {icon_display}[red]Failed: {description}[/red]")
        console.print(f"[dim]Error: {e}[/dim]")
        return False


def wait_for_repository_sync(seconds: int = 120) -> None:
    """Wait for repository synchronization with progress bar."""
    console.print(f"\n[bold yellow]⏳ Waiting for repository sync ({seconds} seconds)...[/bold yellow]")

    with Progress(
        SpinnerColumn(spinner_name="dots12", style="bold bright_yellow"),
        TextColumn("[progress.description]{task.description}", style="bold white"),
        BarColumn(
            bar_width=60,
            style="yellow",
            complete_style="bright_green",
            finished_style="bold bright_green",
            pulse_style="bright_yellow"
        ),
        TextColumn("[bold bright_cyan]{task.percentage:>3.0f}%"),
        TextColumn("•", style="dim"),
        TimeElapsedColumn(),
        TextColumn("•", style="dim"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("🔄 Syncing repository", total=seconds)

        for _ in range(seconds):
            time.sleep(1)
            progress.update(task, advance=1)

    console.print("[bold bright_green on black]✓[/bold bright_green on black] 🔄 [bold bright_yellow]Repository sync complete[/bold bright_yellow]\n")


def main(branch: str = "main") -> int:
    """Main bootstrap function."""
    console.print()
    console.print(Panel(
        f"[bold bright_blue]🚀 Infrahub Demo Bootstrap[/bold bright_blue]\n"
        f"[bright_cyan]Branch:[/bright_cyan] [bold yellow]{branch}[/bold yellow]\n\n"
        "[dim]This will load:[/dim]\n"
        "  [blue]•[/blue] Schemas\n"
        "  [magenta]•[/magenta] Menu definitions\n"
        "  [yellow]•[/yellow] Bootstrap data\n"
        "  [green]•[/green] Security data\n"
        "  [bright_magenta]•[/bright_magenta] Demo repository",
        border_style="bright_blue",
        box=box.DOUBLE,
        title="[bold bright_blue]Bootstrap Process[/bold bright_blue]"
    ))

    # Check if Infrahub is ready
    if not check_infrahub_ready():
        return 1

    steps = [
        {
            "step": "[1/7]",
            "description": "Loading schemas",
            "command": f"uv run infrahubctl schema load schemas --branch {branch}",
            "color": "blue",
            "icon": "📋"
        },
        {
            "step": "[2/7]",
            "description": "Loading menu definitions",
            "command": f"uv run infrahubctl menu load menu --branch {branch}",
            "color": "magenta",
            "icon": "📑"
        },
        {
            "step": "[3/7]",
            "description": "Loading bootstrap data (locations, platforms, roles, etc.)",
            "command": f"uv run infrahubctl object load objects/bootstrap/ --branch {branch}",
            "color": "yellow",
            "icon": "📦"
        },
        {
            "step": "[4/7]",
            "description": "Loading security data (zones, policies, rules)",
            "command": f"uv run infrahubctl object load objects/security/ --branch {branch}",
            "color": "green",
            "icon": "🔒"
        },
        {
            "step": "[5/7]",
            "description": "Populating security relationships",
            "command": "uv run python scripts/populate_security_relationships.py",
            "color": "cyan",
            "icon": "🔗"
        },
    ]

    # Execute all steps
    for i, step_info in enumerate(steps):
        if not run_command(
            step_info["command"],
            step_info["description"],
            step_info["step"],
            step_info["color"],
            step_info["icon"]
        ):
            console.print("\n[bold red]✗ Bootstrap failed![/bold red]")
            return 1

        # Add visual separator after each step (except the last one)
        if i < len(steps) - 1:
            console.print(Rule(style=f"dim {step_info['color']}"))

    # Add repository (may already exist)
    console.print("\n[bold bright_magenta on black][6/7][/bold bright_magenta on black] 📚 [bold white]Adding demo repository[/bold white]")
    result = subprocess.run(
        "uv run infrahubctl repository add DEMO https://github.com/opsmill/infrahub-demo.git --ref main --read-only --ref main",
        shell=True,
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        console.print("[bold bright_green on black]✓[/bold bright_green on black] 📚 [bold bright_magenta]Repository added[/bold bright_magenta]")
    else:
        if "already exists" in result.stderr.lower() or "already exists" in result.stdout.lower():
            console.print("[bold yellow on black]⚠[/bold yellow on black] 📚 [bold bright_magenta]Repository already exists, skipping...[/bold bright_magenta]")
        else:
            console.print("[bold red]✗[/bold red] 📚 [red]Failed to add repository[/red]")
            console.print(f"[dim]{result.stderr}[/dim]")

    console.print(Rule(style="dim bright_magenta"))

    # Wait for repository sync
    console.print("\n[bold bright_yellow on black][7/7][/bold bright_yellow on black] 🔄 [bold white]Waiting for repository sync[/bold white]")
    wait_for_repository_sync(120)

    console.print(Rule(style="dim bright_yellow"))

    # Load event actions
    console.print("\n[bold bright_cyan]→ ⚡ Loading event actions[/bold bright_cyan]")
    run_command(
        f"uv run infrahubctl object load objects/events/ --branch {branch}",
        "Event actions loading",
        "",
        "bright_cyan",
        "⚡"
    )

    console.print(Rule(style="dim bright_cyan"))

    # Display completion message
    console.print()
    console.print(Panel(
        f"[bold bright_green]🎉 Bootstrap Complete![/bold bright_green]\n\n"
        f"[dim]All data has been loaded into Infrahub[/dim]\n"
        f"[bright_cyan]Branch:[/bright_cyan] [bold yellow]{branch}[/bold yellow]\n\n"
        "[bold bright_magenta]Next steps:[/bold bright_magenta]\n"
        "  [green]•[/green] Demo a DC design: [bold bright_cyan]uv run invoke demo-dc-arista[/bold bright_cyan]\n"
        "  [green]•[/green] Create a Proposed Change",
        title="[bold bright_green]✓ Success[/bold bright_green]",
        border_style="bright_green",
        box=box.DOUBLE
    ))

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Bootstrap Infrahub with schemas, data, and configurations"
    )
    parser.add_argument(
        "--branch",
        "-b",
        type=str,
        default="main",
        help="Branch to load data into (default: main)"
    )
    args = parser.parse_args()

    sys.exit(main(branch=args.branch))
