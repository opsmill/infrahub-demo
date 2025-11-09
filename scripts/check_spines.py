#!/usr/bin/env python3
"""Check if spine devices exist and have required data."""

import asyncio
import os
from infrahub_sdk import InfrahubClient


async def main():
    """Check spine devices on add-dc3 branch."""
    client = InfrahubClient(config={"default_branch": "add-dc3"})

    print("Fetching devices with role='spine' on branch 'add-dc3'...")

    # Query for all devices (not just spines)
    query = """
    query {
      DcimGenericDevice {
        count
        edges {
          node {
            id
            name { value }
            role { value }
            primary_address {
              node {
                id
                address { value }
              }
            }
            device_type {
              node {
                name { value }
                platform {
                  node {
                    name { value }
                    netmiko_device_type { value }
                  }
                }
              }
            }
          }
        }
      }
    }
    """

    result = await client.execute_graphql(query=query)

    if "errors" in result:
        print(f"❌ GraphQL Error: {result['errors']}")
        return

    devices = result.get("data", {}).get("DcimGenericDevice", {})
    count = devices.get("count", 0)
    edges = devices.get("edges", [])

    print(f"\n✓ Found {count} spine device(s)")

    for edge in edges:
        device = edge["node"]
        name = device["name"]["value"]
        role = device["role"]["value"]
        primary_addr = device.get("primary_address")
        device_type = device.get("device_type", {}).get("node", {}).get("name", {}).get("value", "N/A")
        platform = device.get("device_type", {}).get("node", {}).get("platform", {}).get("node", {}).get("name", {}).get("value", "N/A")

        print(f"\n  Device: {name}")
        print(f"    Role: {role}")
        print(f"    Type: {device_type}")
        print(f"    Platform: {platform}")

        if primary_addr and primary_addr.get("node"):
            addr = primary_addr["node"].get("address", {}).get("value", "N/A")
            print(f"    Primary Address: {addr}")
        else:
            print(f"    Primary Address: ⚠️  NOT SET (this may cause artifact generation to fail)")


if __name__ == "__main__":
    asyncio.run(main())
