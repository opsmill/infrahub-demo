#!/usr/bin/env python3
"""
Extract device configurations and topologies from Infrahub artifacts.

This script fetches generated configurations from Infrahub and saves them
to the local filesystem for version control and deployment.

Usage:
    python scripts/get_configs.py                    # Use main branch
    python scripts/get_configs.py --branch add-dc3   # Use specific branch
"""

import argparse
import asyncio
import sys
from pathlib import Path

from infrahub_sdk import InfrahubClient
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()


async def get_containerlab_topologies(client: InfrahubClient) -> list[str]:
    """Fetch containerlab topology artifacts and save to files."""
    directory_path = Path("./generated-configs/clab")
    directory_path.mkdir(parents=True, exist_ok=True)

    console.print("\n[cyan]→[/cyan] Fetching containerlab topologies...")

    topologies = await client.all(kind="TopologyDataCenter")

    saved_topologies = []
    for topology in topologies:
        try:
            # Check if topology has containerlab-topology artifact
            await topology.artifacts.fetch()

            has_clab_artifact = False
            for artifact in topology.artifacts.peers:
                if artifact.display_label == "containerlab-topology":
                    has_clab_artifact = True
                    break

            if has_clab_artifact:
                # Fetch artifact content
                artifact_content = await topology.artifact_fetch(
                    "containerlab-topology"
                )
                output_file = directory_path / f"{topology.name.value}.clab.yml"
                with open(output_file, "w") as file:
                    file.write(artifact_content)
                console.print(
                    f"  [green]✓[/green] Saved topology: [bold]{output_file}[/bold]"
                )
                saved_topologies.append(topology.name.value)
        except Exception as e:
            console.print(
                f"  [red]✗[/red] Error fetching topology {topology.name.value}: [dim]{e}[/dim]"
            )

    if len(saved_topologies) == 0:
        console.print("  [yellow]No containerlab topologies found[/yellow]")

    return saved_topologies


async def get_device_configs(client: InfrahubClient) -> int:
    """Fetch device configuration artifacts and save to files."""
    base_path = Path("./generated-configs/devices")
    base_path.mkdir(parents=True, exist_ok=True)

    console.print("\n[cyan]→[/cyan] Fetching device configurations...")

    devices = await client.all(kind="DcimGenericDevice")

    # Artifact names to look for (from .infrahub.yml)
    artifact_names = [
        "leaf",
        "spine",
        "edge",
        "border-leaf",
        "loadbalancer",
        "juniper-firewall",
        "openconfig-leaf",
    ]

    config_count = 0
    for device in devices:
        try:
            # Fetch artifacts list
            await device.artifacts.fetch()

            for artifact in device.artifacts.peers:
                artifact_label = str(artifact.display_label)

                # Check if this is one of our config artifacts
                if artifact_label in artifact_names:
                    # Fetch artifact content
                    artifact_content = await device.artifact_fetch(artifact_label)

                    # Determine file extension based on content type
                    if artifact_label == "openconfig-leaf":
                        extension = "json"
                    else:
                        extension = "cfg"

                    # Save the configuration directly in devices folder
                    output_file = base_path / f"{device.name.value}.{extension}"
                    with open(output_file, "w") as file:
                        file.write(artifact_content)

                    console.print(
                        f"  [green]✓[/green] Saved [bold]{device.name.value}.{extension}[/bold]"
                    )
                    config_count += 1

        except Exception as e:
            console.print(
                f"  [red]✗[/red] Error fetching config for {device.name.value}: [dim]{e}[/dim]"
            )

    if config_count == 0:
        console.print("  [yellow]No device configurations found[/yellow]")

    return config_count


async def get_topology_cabling(client: InfrahubClient) -> int:
    """Fetch topology cabling matrix artifacts and save to files."""
    directory_path = Path("./generated-configs/cabling")
    directory_path.mkdir(parents=True, exist_ok=True)

    console.print("\n[cyan]→[/cyan] Fetching topology cabling matrices...")

    topologies = await client.all(kind="TopologyDataCenter")

    cabling_count = 0
    for topology in topologies:
        try:
            # Check if topology has cabling artifact
            await topology.artifacts.fetch()

            has_cabling_artifact = False
            for artifact in topology.artifacts.peers:
                if artifact.display_label == "topology-cabling":
                    has_cabling_artifact = True
                    break

            if has_cabling_artifact:
                # Fetch artifact content
                artifact_content = await topology.artifact_fetch("topology-cabling")
                output_file = directory_path / f"{topology.name.value}-cabling.txt"
                with open(output_file, "w") as file:
                    file.write(artifact_content)
                console.print(
                    f"  [green]✓[/green] Saved cabling matrix: [bold]{output_file}[/bold]"
                )
                cabling_count += 1
        except Exception as e:
            console.print(
                f"  [red]✗[/red] Error fetching cabling for {topology.name.value}: [dim]{e}[/dim]"
            )

    if cabling_count == 0:
        console.print("  [yellow]No cabling matrices found[/yellow]")

    return cabling_count


async def main(branch: str | None = None) -> int:
    """Main function to fetch all artifacts."""
    # Connect to Infrahub with branch configuration
    branch_name = branch if branch else "main"

    console.print()
    console.print(
        Panel(
            f"[bold cyan]Extracting Infrahub Configuration Artifacts[/bold cyan]\n"
            f"[dim]Branch:[/dim] {branch_name}",
            border_style="cyan",
            box=box.SIMPLE,
        )
    )

    if branch:
        client = InfrahubClient(config={"default_branch": branch})
    else:
        client = InfrahubClient()

    # Fetch all artifact types and track results
    saved_topologies = await get_containerlab_topologies(client)
    config_count = await get_device_configs(client)
    cabling_count = await get_topology_cabling(client)

    # Check if any artifacts were retrieved
    topology_count = len(saved_topologies)
    total_artifacts = topology_count + config_count + cabling_count

    console.print()

    if total_artifacts == 0:
        # Display error panel if no artifacts were found
        console.print(
            Panel(
                "[bold red]✗ Artifact Extraction Failed![/bold red]\n\n"
                "[yellow]No artifacts were retrieved from Infrahub.[/yellow]\n\n"
                "[dim]Possible causes:[/dim]\n"
                "  • The branch may not have any generated artifacts yet\n"
                "  • The topology generator may not have been run\n"
                "  • Artifacts may have failed to generate\n\n"
                "[cyan]Next steps:[/cyan]\n"
                f"  • Check the branch exists: [bold]uv run infrahubctl branch list[/bold]\n"
                f'  • Run the generator: [bold]uv run infrahubctl generator create_dc --branch {branch_name} name="<topology-name>"[/bold]\n'
                "  • Check Infrahub logs for errors",
                title="[bold red]Error[/bold red]",
                border_style="red",
                box=box.SIMPLE,
            )
        )
        return 1

    # Display success panel if artifacts were found
    console.print(
        Panel(
            "[bold green]Configuration extraction complete![/bold green]\n\n"
            f"[dim]Retrieved:[/dim]\n"
            f"  • [cyan]{topology_count}[/cyan] containerlab topolog{'y' if topology_count == 1 else 'ies'}\n"
            f"  • [cyan]{config_count}[/cyan] device configuration{'s' if config_count != 1 else ''}\n"
            f"  • [cyan]{cabling_count}[/cyan] cabling matri{'x' if cabling_count == 1 else 'ces'}\n\n"
            f"[dim]Saved to:[/dim] [bold]./generated-configs/[/bold]",
            border_style="green",
            box=box.SIMPLE,
        )
    )

    # Display containerlab deployment instructions if topologies were saved
    if saved_topologies:
        console.print()

        # Create deployment table
        deploy_table = Table(
            title="Containerlab Deployment Commands",
            box=box.SIMPLE,
            show_header=True,
            header_style="bold magenta",
        )
        deploy_table.add_column("Action", style="cyan", no_wrap=True)
        deploy_table.add_column("Command", style="white")

        for topology_name in saved_topologies:
            deploy_cmd = f"sudo -E containerlab deploy -t generated-configs/clab/{topology_name}.clab.yml"
            destroy_cmd = f"sudo -E containerlab destroy -t generated-configs/clab/{topology_name}.clab.yml"

            deploy_table.add_row(
                f"Deploy {topology_name}", f"[green]{deploy_cmd}[/green]"
            )
            deploy_table.add_row(
                f"Destroy {topology_name}", f"[red]{destroy_cmd}[/red]"
            )

        console.print(deploy_table)
        console.print()

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract device configurations from Infrahub"
    )
    parser.add_argument(
        "--branch",
        "-b",
        type=str,
        help="Branch to fetch artifacts from (default: main)",
        default=None,
    )
    args = parser.parse_args()

    exit_code = asyncio.run(main(branch=args.branch))
    sys.exit(exit_code)
