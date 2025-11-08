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
from pathlib import Path

from infrahub_sdk import InfrahubClient


async def get_containerlab_topologies(client: InfrahubClient) -> list[str]:
    """Fetch containerlab topology artifacts and save to files."""
    directory_path = Path("./generated-configs/clab")
    directory_path.mkdir(parents=True, exist_ok=True)

    print("Fetching containerlab topologies...")

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
                artifact_content = await topology.artifact_fetch("containerlab-topology")
                output_file = directory_path / f"{topology.name.value}.clab.yml"
                with open(output_file, "w") as file:
                    file.write(artifact_content)
                print(f"  ✓ Saved topology: {output_file}")
                saved_topologies.append(topology.name.value)
        except Exception as e:
            print(f"  ✗ Error fetching topology {topology.name.value}: {e}")

    if len(saved_topologies) == 0:
        print("  No containerlab topologies found")
    print()

    return saved_topologies


async def get_device_configs(client: InfrahubClient) -> None:
    """Fetch device configuration artifacts and save to files."""
    base_path = Path("./generated-configs/devices")
    base_path.mkdir(parents=True, exist_ok=True)

    print("Fetching device configurations...")

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

                    print(f"  ✓ Saved {device.name.value}.{extension}")
                    config_count += 1

        except Exception as e:
            print(f"  ✗ Error fetching config for {device.name.value}: {e}")

    if config_count == 0:
        print("  No device configurations found")
    print()


async def get_topology_cabling(client: InfrahubClient) -> None:
    """Fetch topology cabling matrix artifacts and save to files."""
    directory_path = Path("./generated-configs/cabling")
    directory_path.mkdir(parents=True, exist_ok=True)

    print("Fetching topology cabling matrices...")

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
                print(f"  ✓ Saved cabling matrix: {output_file}")
                cabling_count += 1
        except Exception as e:
            print(f"  ✗ Error fetching cabling for {topology.name.value}: {e}")

    if cabling_count == 0:
        print("  No cabling matrices found")
    print()


async def main(branch: str | None = None) -> None:
    """Main function to fetch all artifacts."""
    # Connect to Infrahub with branch configuration
    if branch:
        print(f"Using branch: {branch}")
        client = InfrahubClient(config={"default_branch": branch})
    else:
        print("Using main branch")
        client = InfrahubClient()

    print("\n" + "=" * 60)
    print("Extracting Infrahub Configuration Artifacts")
    print("=" * 60 + "\n")

    # Fetch all artifact types
    saved_topologies = await get_containerlab_topologies(client)
    await get_device_configs(client)
    await get_topology_cabling(client)

    print("=" * 60)
    print("Configuration extraction complete!")
    print("Configs saved to: ./generated-configs/")
    print("=" * 60 + "\n")

    # Display containerlab deployment instructions if topologies were saved
    if saved_topologies:
        print("=" * 60)
        print("Deploy with Containerlab")
        print("=" * 60 + "\n")
        print("To deploy a data center topology in Containerlab, use:\n")
        for topology_name in saved_topologies:
            print(f"  sudo -E containerlab deploy -t generated-configs/clab/{topology_name}.clab.yml")
        print("\nTo destroy a topology:")
        for topology_name in saved_topologies:
            print(f"  sudo -E containerlab destroy -t generated-configs/clab/{topology_name}.clab.yml")
        print("\n" + "=" * 60 + "\n")


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

    asyncio.run(main(branch=args.branch))
