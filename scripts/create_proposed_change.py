#!/usr/bin/env python3
"""
Create an Infrahub Proposed Change.

This script creates a proposed change from a branch, which allows for
reviewing and validating changes before merging them to the main branch.

Usage:
    python scripts/create_proposed_change.py                    # Use add-dc3 branch
    python scripts/create_proposed_change.py --branch my-branch  # Use specific branch
"""

import argparse
import asyncio
import sys

from infrahub_sdk import InfrahubClient
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import box

console = Console()


async def create_proposed_change(branch: str) -> int:
    """
    Create a proposed change for the specified branch.

    Args:
        branch: The branch name to create a proposed change for

    Returns:
        0 on success, 1 on failure
    """
    console.print()
    console.print(Panel(
        f"[bold bright_magenta]🚀 Creating Infrahub Proposed Change[/bold bright_magenta]\n\n"
        f"[bright_cyan]Source Branch:[/bright_cyan] [bold yellow]{branch}[/bold yellow]\n"
        f"[bright_cyan]Target Branch:[/bright_cyan] [bold green]main[/bold green]",
        border_style="bright_magenta",
        box=box.DOUBLE,
        title="[bold bright_white]Proposed Change[/bold bright_white]",
        title_align="left"
    ))

    # Connect to Infrahub
    console.print("\n[cyan]→[/cyan] Connecting to Infrahub...")

    try:
        client = InfrahubClient()
        console.print(f"[green]✓[/green] Connected to Infrahub at [bold]{client.address}[/bold]")
    except Exception as e:
        console.print(f"[red]✗ Failed to connect to Infrahub:[/red] {e}")
        return 1

    # Check if branch exists
    console.print(f"\n[cyan]→[/cyan] Checking if branch [bold]{branch}[/bold] exists...")

    try:
        branches = await client.branch.all()
        branch_names = [b.name for b in branches]

        if branch not in branch_names:
            console.print(f"[red]✗ Branch '[bold]{branch}[/bold]' does not exist[/red]")
            console.print("\n[yellow]Available branches:[/yellow]")
            for b in branch_names[:10]:  # Show first 10
                console.print(f"  • {b}")
            return 1

        console.print(f"[green]✓[/green] Branch [bold]{branch}[/bold] exists")
    except Exception as e:
        console.print(f"[red]✗ Error checking branches:[/red] {e}")
        return 1

    # Create proposed change
    console.print("\n[yellow]→[/yellow] Creating proposed change...")

    try:
        with Progress(
            SpinnerColumn(spinner_name="dots12", style="bold bright_yellow"),
            TextColumn("[progress.description]{task.description}", style="bold white"),
            console=console,
        ) as progress:
            progress.add_task(f"Creating proposed change for '{branch}'", total=None)

            # Create the proposed change
            proposed_change = await client.create(
                kind="CoreProposedChange",
                data={
                    "name": {"value": f"Proposed change for {branch}"},
                    "description": {"value": f"Automated proposed change created for branch {branch}"},
                    "source_branch": {"value": branch},
                    "destination_branch": {"value": "main"},
                }
            )

            await proposed_change.save()
            progress.stop()

        console.print("[green]✓[/green] Proposed change created successfully!")

        # Display proposed change details
        console.print()
        details_table = Table(
            title="✨ Proposed Change Details",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold bright_cyan",
            border_style="bright_green"
        )
        details_table.add_column("Property", style="bright_cyan", no_wrap=True)
        details_table.add_column("Value", style="bright_white")

        details_table.add_row("ID", f"[bold yellow]{proposed_change.id}[/bold yellow]")
        details_table.add_row("Name", f"[bold]{proposed_change.name.value}[/bold]")
        details_table.add_row("Source Branch", f"[bold yellow]{branch}[/bold yellow]")
        details_table.add_row("Destination Branch", "[bold green]main[/bold green]")
        details_table.add_row("State", f"[bold bright_magenta]{proposed_change.state.value if hasattr(proposed_change, 'state') else 'open'}[/bold bright_magenta]")

        console.print(details_table)
        console.print()

        # Show URL
        pc_url = f"{client.address}/proposed-changes/{proposed_change.id}"
        console.print(Panel(
            f"[bold bright_white]View Proposed Change:[/bold bright_white]\n\n"
            f"[bright_blue]{pc_url}[/bright_blue]",
            border_style="bright_green",
            box=box.ROUNDED
        ))

        console.print()
        console.print("[bold bright_green]🎉 Success![/bold bright_green] Proposed change is ready for review.\n")

        return 0

    except Exception as e:
        console.print(f"[red]✗ Failed to create proposed change:[/red] {e}")

        # Show helpful error information
        if "already exists" in str(e).lower():
            console.print("\n[yellow]💡 Tip:[/yellow] A proposed change for this branch may already exist.")
            console.print("   Check the Infrahub UI or delete the existing proposed change first.")

        return 1


async def main(branch: str | None = None) -> int:
    """Main function to create proposed change."""
    branch_name = branch if branch else "add-dc3"
    return await create_proposed_change(branch_name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create an Infrahub Proposed Change from a branch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create proposed change for add-dc3 branch (default)
  python scripts/create_proposed_change.py

  # Create proposed change for a specific branch
  python scripts/create_proposed_change.py --branch my-feature-branch

  # Using invoke
  uv run invoke create-pc
  uv run invoke create-pc --branch my-feature-branch
        """
    )
    parser.add_argument(
        "--branch",
        "-b",
        type=str,
        help="Branch to create proposed change for (default: add-dc3)",
        default=None,
    )
    args = parser.parse_args()

    exit_code = asyncio.run(main(branch=args.branch))
    sys.exit(exit_code)
