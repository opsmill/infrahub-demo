#!/usr/bin/env python3
"""Populate many-to-many relationships for security objects.

This script populates the relationships that cannot be easily defined in YAML files
due to limitations with infrahubctl object load for many-to-many relationships.

Run this after loading the security objects:
    uv run python scripts/populate_security_relationships.py
"""

import asyncio
import sys
from infrahub_sdk import InfrahubClient, Config


async def populate_address_groups(client: InfrahubClient) -> None:
    """Populate SecurityAddressGroup relationships."""
    print("\n📦 Populating Address Group Relationships...")

    # Populate web-servers group
    web_servers_group = await client.get(kind="SecurityAddressGroup", name__value="web-servers")
    if web_servers_group:
        print(f"  Found: {web_servers_group.name.value}")
        await web_servers_group.ip_addresses.fetch()

        web_server_01 = await client.get(kind="SecurityIPAddress", name__value="web-server-01")
        web_server_02 = await client.get(kind="SecurityIPAddress", name__value="web-server-02")

        if web_server_01 and web_server_02:
            web_servers_group.ip_addresses.add(web_server_01.id)
            web_servers_group.ip_addresses.add(web_server_02.id)
            await web_servers_group.save()
            print("  ✅ Added web-server-01 and web-server-02 to web-servers group")
        else:
            print("  ⚠️  Could not find web server IP addresses")
    else:
        print("  ⚠️  Could not find web-servers group")

    # Populate internet group
    internet_group = await client.get(kind="SecurityAddressGroup", name__value="internet")
    if internet_group:
        print(f"  Found: {internet_group.name.value}")
        await internet_group.prefixes.fetch()

        internet_prefix = await client.get(kind="SecurityPrefix", name__value="internet")

        if internet_prefix:
            internet_group.prefixes.add(internet_prefix.id)
            await internet_group.save()
            print("  ✅ Added internet prefix to internet group")
        else:
            print("  ⚠️  Could not find internet prefix")
    else:
        print("  ⚠️  Could not find internet group")


async def populate_service_groups(client: InfrahubClient) -> None:
    """Populate SecurityServiceGroup relationships."""
    print("\n🔧 Populating Service Group Relationships...")

    # Populate web-services group
    web_services_group = await client.get(kind="SecurityServiceGroup", name__value="web-services")
    if web_services_group:
        print(f"  Found: {web_services_group.name.value}")
        await web_services_group.services.fetch()

        https_service = await client.get(kind="SecurityService", name__value="https")

        if https_service:
            web_services_group.services.add(https_service.id)
            await web_services_group.save()
            print("  ✅ Added https service to web-services group")
        else:
            print("  ⚠️  Could not find https service")
    else:
        print("  ⚠️  Could not find web-services group")


async def main() -> int:
    """Main entry point."""
    print("🚀 Populating Security Object Relationships\n")

    try:
        config = Config(
            address="http://localhost:8000",
            api_token="06438eb2-8019-4776-878c-0941b1f1d1ec"
        )
        client = InfrahubClient(config=config)

        await populate_address_groups(client)
        await populate_service_groups(client)

        print("\n✅ All relationships populated successfully!\n")
        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
