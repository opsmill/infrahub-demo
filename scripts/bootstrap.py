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
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich import box

console = Console()

INFRAHUB_ADDRESS = "http://localhost:8000"


def check_infrahub_ready(max_retries: int = 30, sleep_time: int = 2) -> bool:
    """Check if Infrahub is ready to accept requests."""
    console.print("\n[cyan]→[/cyan] Checking if Infrahub is ready...")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Waiting for Infrahub...", total=max_retries)

        for attempt in range(max_retries):
            try:
                response = requests.get(f"{INFRAHUB_ADDRESS}/api/schema", timeout=2)
                if response.status_code == 200:
                    progress.update(task, completed=max_retries)
                    console.print("[green]✓[/green] Infrahub is ready!\n")
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


def run_command(command: str, description: str, step: str) -> bool:
    """Run a shell command and display output."""
    console.print(f"\n[cyan]{step}[/cyan] {description}")

    try:
        subprocess.run(
            command,
            shell=True,
            check=True,
            capture_output=False,
            text=True
        )
        console.print(f"[green]✓[/green] {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗[/red] Failed: {description}")
        console.print(f"[dim]Error: {e}[/dim]")
        return False


def wait_for_repository_sync(seconds: int = 120) -> None:
    """Wait for repository synchronization with progress bar."""
    console.print(f"\n[cyan]→[/cyan] Waiting for repository sync ({seconds} seconds)...")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Syncing repository...", total=seconds)

        for _ in range(seconds):
            time.sleep(1)
            progress.update(task, advance=1)

    console.print("[green]✓[/green] Repository sync complete\n")


def main(branch: str = "main") -> int:
    """Main bootstrap function."""
    console.print()
    console.print(Panel(
        f"[bold blue]Infrahub Demo Bootstrap[/bold blue]\n"
        f"[dim]Branch:[/dim] [bold]{branch}[/bold]\n\n"
        "[dim]This will load schemas, menu, bootstrap data, security, and repository[/dim]",
        border_style="blue",
        box=box.ROUNDED,
        title="Bootstrap Process"
    ))

    # Check if Infrahub is ready
    if not check_infrahub_ready():
        return 1

    steps = [
        {
            "step": "[1/7]",
            "description": "Loading schemas",
            "command": f"uv run infrahubctl schema load schemas --branch {branch}"
        },
        {
            "step": "[2/7]",
            "description": "Loading menu definitions",
            "command": f"uv run infrahubctl menu load menu --branch {branch}"
        },
        {
            "step": "[3/7]",
            "description": "Loading bootstrap data (locations, platforms, roles, etc.)",
            "command": f"uv run infrahubctl object load objects/bootstrap/ --branch {branch}"
        },
        {
            "step": "[4/7]",
            "description": "Loading security data (zones, policies, rules)",
            "command": f"uv run infrahubctl object load objects/security/ --branch {branch}"
        },
        {
            "step": "[5/7]",
            "description": "Populating security relationships",
            "command": "uv run python scripts/populate_security_relationships.py"
        },
    ]

    # Execute all steps
    for step_info in steps:
        if not run_command(
            step_info["command"],
            step_info["description"],
            step_info["step"]
        ):
            console.print("\n[red]Bootstrap failed![/red]")
            return 1

    # Add repository (may already exist)
    console.print("\n[cyan][6/7][/cyan] Adding demo repository")
    result = subprocess.run(
        "uv run infrahubctl repository add DEMO https://github.com/opsmill/infrahub-demo.git --ref main --read-only --ref main",
        shell=True,
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        console.print("[green]✓[/green] Repository added")
    else:
        if "already exists" in result.stderr.lower() or "already exists" in result.stdout.lower():
            console.print("[yellow]⚠[/yellow] Repository already exists, skipping...")
        else:
            console.print("[red]✗[/red] Failed to add repository")
            console.print(f"[dim]{result.stderr}[/dim]")

    # Wait for repository sync
    console.print("\n[cyan][7/7][/cyan] Waiting for repository sync")
    wait_for_repository_sync(120)

    # Load event actions
    console.print("\n[cyan]→[/cyan] Loading event actions")
    if run_command(
        f"uv run infrahubctl object load objects/events/ --branch {branch}",
        "Event actions loading",
        ""
    ):
        console.print("[green]✓[/green] Event actions loaded successfully")

    # Display completion message
    console.print()
    console.print(Panel(
        f"[bold green]Bootstrap Complete![/bold green]\n\n"
        f"[dim]All data has been loaded into Infrahub[/dim]\n"
        f"[dim]Branch:[/dim] [bold]{branch}[/bold]\n\n"
        "[cyan]Next steps:[/cyan]\n"
        "  • Demo a DC design: [bold]uv run invoke demo-dc-arista[/bold]\n"
        "  • Create a Proposed Change",
        title="Success",
        border_style="green",
        box=box.ROUNDED
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
