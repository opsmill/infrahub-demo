#!/usr/bin/env python3
"""
Create an Infrahub Proposed Change for reviewing branch changes before merging.

This script automates the creation of Proposed Changes in Infrahub, which provide
a controlled workflow for reviewing, validating, and approving infrastructure
changes before merging them to the main branch.

What is a Proposed Change?
==========================
A Proposed Change is Infrahub's change management mechanism that:
- Creates a review workflow for branch changes before merging to main
- Runs validation checks (generators, transforms, checks) on the proposed changes
- Provides a visual diff showing what will change when merged
- Allows team collaboration and approval before changes go live
- Generates artifacts (configs, topologies) for the proposed state
- Tracks the change lifecycle (open, merged, closed, canceled)

Why Use Proposed Changes?
==========================
1. **Risk Mitigation**: Review changes before they affect production
2. **Validation**: Automatically run checks to verify configuration correctness
3. **Collaboration**: Team members can review and approve changes
4. **Audit Trail**: Track who proposed and approved infrastructure changes
5. **Preview**: See generated configurations before applying changes
6. **Rollback**: Changes can be canceled if issues are discovered

Workflow Integration:
=====================
This script is typically used after creating a branch and loading demo data:
1. Create branch: `uv run infrahubctl branch create my-branch`
2. Load data: `uv run infrahubctl object load objects/dc/dc-arista-s.yml --branch my-branch`
3. Run generator: Via Infrahub UI or API to create topology
4. Create PC: `uv run python scripts/create_proposed_change.py --branch my-branch`
5. Review PC: Open the URL in browser to see validations and diffs
6. Merge PC: Approve and merge via Infrahub UI

Features:
=========
- Rich terminal UI with color-coded status indicators
- Automatic Infrahub connection and authentication
- Branch existence validation before creating Proposed Change
- Beautiful progress indicators during creation
- Detailed information table showing PC properties
- Direct URL link to view the Proposed Change in browser
- Helpful error messages with troubleshooting tips

Error Handling:
===============
- Validates Infrahub connectivity before proceeding
- Checks if branch exists (with graceful fallback)
- Detects duplicate Proposed Changes and provides helpful tips
- Clear error messages with remediation guidance

Usage:
======
    # Create proposed change for default branch (add-dc3)
    python scripts/create_proposed_change.py

    # Create proposed change for specific branch
    python scripts/create_proposed_change.py --branch my-feature-branch
    python scripts/create_proposed_change.py -b dc-juniper

    # Via invoke task (from tasks.py)
    uv run invoke create-pc --branch my-branch

Environment Variables:
======================
    INFRAHUB_ADDRESS: Infrahub server URL (default: http://localhost:8000)
    INFRAHUB_API_TOKEN: API token for authentication (if required)

Output:
=======
The script displays:
- Connection status with Infrahub server address
- Branch existence verification
- Creation progress with spinner animation
- Proposed Change details table (ID, Name, Source, Destination, State)
- Direct URL link to view in browser
- Success confirmation message

Exit Codes:
===========
    0: Proposed Change created successfully
    1: Failed to create (connection error, branch doesn't exist, duplicate PC, etc.)
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

# ============================================================================
# CONFIGURATION AND SETUP
# ============================================================================

# Initialize Rich console for beautiful terminal output with color support
console = Console()


# ============================================================================
# CORE FUNCTIONALITY
# ============================================================================


async def create_proposed_change(branch: str) -> int:
    """
    Create an Infrahub Proposed Change from a branch to main.

    This function orchestrates the complete Proposed Change creation workflow:
    1. Display welcome panel with source/destination branch information
    2. Connect to Infrahub using SDK client with environment-based config
    3. Verify that the source branch exists in Infrahub
    4. Create the CoreProposedChange object via GraphQL mutation
    5. Display detailed information about the created Proposed Change
    6. Provide direct URL link to view in browser

    What Happens in Infrahub:
    ==========================
    When a Proposed Change is created, Infrahub automatically:
    - Creates a CoreProposedChange object with metadata
    - Initiates validation checks on the branch changes
    - Generates artifacts (configurations, topologies) for review
    - Prepares a visual diff of what will change when merged
    - Makes the PC available in the UI for team review

    Visual Feedback:
    ================
    - Welcome panel with branch names in color-coded format
    - Connection status with Infrahub server address
    - Branch verification status (with graceful fallback if unavailable)
    - Spinner animation during PC creation
    - Detailed table showing PC properties (ID, Name, Source, Destination, State)
    - Clickable URL to view the Proposed Change in browser
    - Success confirmation message

    Error Scenarios Handled:
    ========================
    1. Connection failure to Infrahub (network issues, wrong URL)
    2. Branch doesn't exist (user typo, branch not created yet)
    3. Duplicate Proposed Change (PC already exists for this branch)
    4. API errors during PC creation (permissions, validation failures)

    Args:
        branch: The source branch name to create a Proposed Change for.
               This branch will be compared against the main branch.
               The branch must exist in Infrahub before creating a PC.

    Returns:
        0 if Proposed Change created successfully
        1 if creation failed (connection error, branch missing, duplicate, etc.)

    Example:
        >>> # Create PC for a branch containing new DC topology
        >>> exit_code = await create_proposed_change("add-dc3")
        >>> if exit_code == 0:
        ...     print("Proposed Change ready for review!")

        >>> # Create PC for a feature branch
        >>> exit_code = await create_proposed_change("feature-new-security-zones")

    Note:
        The function uses environment variables for Infrahub connection:
        - INFRAHUB_ADDRESS: Server URL (default: http://localhost:8000)
        - INFRAHUB_API_TOKEN: Authentication token (if required)
    """
    console.print()
    console.print(
        Panel(
            f"[bold bright_magenta]🚀 Creating Infrahub Proposed Change[/bold bright_magenta]\n\n"
            f"[bright_cyan]Source Branch:[/bright_cyan] [bold yellow]{branch}[/bold yellow]\n"
            f"[bright_cyan]Target Branch:[/bright_cyan] [bold green]main[/bold green]",
            border_style="bright_magenta",
            box=box.SIMPLE,
            title="[bold bright_white]Proposed Change[/bold bright_white]",
            title_align="left",
        )
    )

    # ========================================================================
    # Step 1: Connect to Infrahub
    # ========================================================================
    # Initialize the Infrahub SDK client which handles:
    # - Reading INFRAHUB_ADDRESS and INFRAHUB_API_TOKEN from environment
    # - Setting up GraphQL client for API communication
    # - Establishing authentication if token is provided
    console.print("\n[cyan]→[/cyan] Connecting to Infrahub...")

    try:
        # InfrahubClient() automatically reads from environment variables
        client = InfrahubClient()
        console.print(
            f"[green]✓[/green] Connected to Infrahub at [bold]{client.address}[/bold]"
        )
    except Exception as e:
        # Connection failures typically indicate:
        # - Infrahub not running (need to run: uv run invoke start)
        # - Wrong INFRAHUB_ADDRESS in environment
        # - Network connectivity issues
        console.print(f"[red]✗ Failed to connect to Infrahub:[/red] {e}")
        return 1

    # ========================================================================
    # Step 2: Verify Branch Existence
    # ========================================================================
    # Validate that the source branch exists before creating a Proposed Change.
    # This prevents errors later and provides early feedback if the user
    # made a typo in the branch name or forgot to create the branch.
    console.print(
        f"\n[cyan]→[/cyan] Checking if branch [bold]{branch}[/bold] exists..."
    )

    try:
        # Query Infrahub API to get the branch object
        # This validates the branch name and ensures it exists
        branch_obj = await client.branch.get(branch)
        if branch_obj:
            console.print(f"[green]✓[/green] Branch [bold]{branch}[/bold] exists")
        else:
            # Branch not found - user needs to create it first
            console.print(f"[red]✗ Branch '[bold]{branch}[/bold]' does not exist[/red]")
            return 1
    except Exception as e:
        # Branch verification failed (API error, permissions, etc.)
        # We warn but continue, as the PC creation may still succeed
        # The actual PC creation will fail if the branch truly doesn't exist
        console.print(f"[yellow]⚠[/yellow] Could not verify branch exists: {e}")
        console.print("[dim]Continuing anyway...[/dim]")

    # ========================================================================
    # Step 3: Create Proposed Change
    # ========================================================================
    # Create a CoreProposedChange object in Infrahub via the SDK.
    # This triggers Infrahub to:
    # - Create the PC object with metadata
    # - Run validation checks on the branch
    # - Generate artifacts for review
    # - Prepare diffs between source and destination branches
    console.print("\n[yellow]→[/yellow] Creating proposed change...")

    try:
        # Display progress indicator while creating the Proposed Change
        # The spinner provides visual feedback during the async operation
        with Progress(
            SpinnerColumn(spinner_name="dots12", style="bold bright_yellow"),
            TextColumn("[progress.description]{task.description}", style="bold white"),
            console=console,
        ) as progress:
            progress.add_task(f"Creating proposed change for '{branch}'", total=None)

            # Create the CoreProposedChange object using the Infrahub SDK
            # This sends a GraphQL mutation to create the object
            proposed_change = await client.create(
                kind="CoreProposedChange",  # Infrahub schema type
                data={
                    "name": {"value": f"Proposed change for {branch}"},
                    "description": {
                        "value": f"Automated proposed change created for branch {branch}"
                    },
                    "source_branch": {"value": branch},  # Branch with changes
                    "destination_branch": {"value": "main"},  # Target branch (usually main)
                },
            )

            # Save the object to Infrahub (commits the GraphQL mutation)
            await proposed_change.save()
            progress.stop()

        console.print("[green]✓[/green] Proposed change created successfully!")

        # ====================================================================
        # Step 4: Display Proposed Change Details
        # ====================================================================
        # Show a formatted table with key information about the created PC.
        # This provides the user with essential details and the PC ID needed
        # for later operations (merge, close, etc.)
        console.print()
        details_table = Table(
            title="✨ Proposed Change Details",
            box=box.SIMPLE,  # ASCII box for terminal compatibility
            show_header=True,
            header_style="bold bright_cyan",
            border_style="bright_green",
            padding=(0, 1),
        )
        details_table.add_column(
            "Property", style="bright_cyan", no_wrap=True, width=20
        )
        details_table.add_column("Value", style="bright_white", width=50)

        # Add rows with PC information
        details_table.add_row("ID", f"[bold yellow]{proposed_change.id}[/bold yellow]")
        details_table.add_row("Name", f"[bold]{proposed_change.name.value}[/bold]")
        details_table.add_row("Source Branch", f"[bold yellow]{branch}[/bold yellow]")
        details_table.add_row("Destination Branch", "[bold green]main[/bold green]")

        # Extract state with fallback handling
        # Newly created PCs may not have a state attribute immediately
        # Default to "open" which is the typical initial state
        state_value = "open"
        if hasattr(proposed_change, "state") and proposed_change.state:
            state_value = (
                proposed_change.state.value
                if hasattr(proposed_change.state, "value")
                else str(proposed_change.state)
            )
        details_table.add_row(
            "State", f"[bold bright_magenta]{state_value}[/bold bright_magenta]"
        )

        console.print(details_table)
        console.print()

        # ====================================================================
        # Step 5: Display URL for Browser Access
        # ====================================================================
        # Construct and display the direct URL to view the Proposed Change
        # in the Infrahub web UI. Users can click this link to:
        # - View the visual diff of changes
        # - See validation check results
        # - Review generated artifacts
        # - Approve and merge the changes
        pc_url = f"{client.address}/proposed-changes/{proposed_change.id}"
        console.print(
            Panel(
                f"[bold bright_white]View Proposed Change:[/bold bright_white]\n\n"
                f"[bright_blue]{pc_url}[/bright_blue]",
                border_style="bright_green",
                box=box.SIMPLE,  # ASCII box for terminal compatibility
            )
        )

        console.print()
        console.print(
            "[bold bright_green]🎉 Success![/bold bright_green] Proposed change is ready for review.\n"
        )

        return 0

    except Exception as e:
        # ====================================================================
        # Error Handling
        # ====================================================================
        # Handle various failure scenarios with helpful error messages
        console.print(f"[red]✗ Failed to create proposed change:[/red] {e}")

        # Check for duplicate Proposed Change error
        # This commonly happens when a PC already exists for the branch
        if "already exists" in str(e).lower():
            console.print(
                "\n[yellow]💡 Tip:[/yellow] A proposed change for this branch may already exist."
            )
            console.print(
                "   Check the Infrahub UI or delete the existing proposed change first."
            )

        return 1


async def main(branch: str | None = None) -> int:
    """
    Main entry point for the Proposed Change creation script.

    This function serves as the async entry point that handles branch name
    defaulting and delegates to the create_proposed_change function.

    Args:
        branch: Optional branch name to create PC for.
               If None, defaults to "add-dc3" (legacy default for demos).

    Returns:
        0 if Proposed Change created successfully, 1 on failure

    Example:
        >>> # Create PC for default branch
        >>> exit_code = await main()

        >>> # Create PC for specific branch
        >>> exit_code = await main(branch="my-feature")
    """
    # Use provided branch name or default to "add-dc3" for backward compatibility
    # "add-dc3" is the default used in demo scenarios
    branch_name = branch if branch else "add-dc3"
    return await create_proposed_change(branch_name)


# ============================================================================
# COMMAND-LINE INTERFACE
# ============================================================================
# This section handles script execution from the command line with argument
# parsing and async execution via asyncio.run().

if __name__ == "__main__":
    # Set up argument parser with custom formatting for help text
    # RawDescriptionHelpFormatter preserves formatting in epilog examples
    parser = argparse.ArgumentParser(
        description="Create an Infrahub Proposed Change from a branch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create proposed change for add-dc3 branch (default)
  python scripts/create_proposed_change.py

  # Create proposed change for a specific branch
  python scripts/create_proposed_change.py --branch my-feature-branch

        """,
    )

    # Add --branch argument to specify which branch to create PC for
    # Default is None, which will be converted to "add-dc3" in main()
    parser.add_argument(
        "--branch",
        "-b",
        type=str,
        help="Branch to create proposed change for (default: add-dc3)",
        default=None,
    )

    # Parse command-line arguments
    args = parser.parse_args()

    # Execute the async main function using asyncio.run()
    # This handles the async event loop setup and teardown
    exit_code = asyncio.run(main(branch=args.branch))

    # Exit with the return code from main (0 = success, 1 = failure)
    sys.exit(exit_code)
