#!/usr/bin/env python3
"""Populate many-to-many relationships for security objects.

This script populates the relationships that cannot be easily defined in YAML files
due to limitations with infrahubctl object load for many-to-many relationships.

Run this after loading the security objects:
    uv run python scripts/populate_security_relationships.py
"""

import asyncio
import os
import sys
from infrahub_sdk import InfrahubClient, Config


async def populate_address_groups(client: InfrahubClient) -> None:
    """Populate SecurityAddressGroup relationships."""
    print("\n📦 Populating Address Group Relationships...")

    # Populate web-servers group
    web_servers_group = await client.get(
        kind="SecurityAddressGroup", name__value="web-servers"
    )
    if web_servers_group:
        print(f"  Found: {web_servers_group.name.value}")
        await web_servers_group.ip_addresses.fetch()

        web_server_01 = await client.get(
            kind="SecurityIPAddress", name__value="web-server-01"
        )
        web_server_02 = await client.get(
            kind="SecurityIPAddress", name__value="web-server-02"
        )

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
    internet_group = await client.get(
        kind="SecurityAddressGroup", name__value="internet"
    )
    if internet_group:
        print(f"  Found: {internet_group.name.value}")
        await internet_group.prefixes.fetch()

        internet_prefix = await client.get(
            kind="SecurityPrefix", name__value="internet"
        )

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
    web_services_group = await client.get(
        kind="SecurityServiceGroup", name__value="web-services"
    )
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


async def populate_firewall_policies(client: InfrahubClient) -> None:
    """Populate SecurityPolicy firewall relationships."""
    print("\n🛡️  Populating Firewall Policy Relationships...")

    # Populate corporate-firewall-policy
    corporate_policy = await client.get(
        kind="SecurityPolicy", name__value="corporate-firewall-policy"
    )
    if corporate_policy:
        print(f"  Found: {corporate_policy.name.value}")
        await corporate_policy.firewalls.fetch()

        corp_firewall = await client.get(
            kind="SecurityFirewall", name__value="corp-firewall"
        )

        if corp_firewall:
            corporate_policy.firewalls.add(corp_firewall.id)
            await corporate_policy.save()
            print("  ✅ Added corp-firewall to corporate-firewall-policy")
        else:
            print("  ⚠️  Could not find corp-firewall")
    else:
        print("  ⚠️  Could not find corporate-firewall-policy")


async def populate_policy_rules(client: InfrahubClient) -> None:
    """Populate SecurityPolicyRule relationships."""
    print("\n📋 Populating Policy Rule Relationships...")

    try:
        # Populate allow-web-traffic rule
        allow_web_rule = await client.get(
            kind="SecurityPolicyRule", name__value="allow-web-traffic"
        )
        if allow_web_rule:
            print(f"  Found: {allow_web_rule.name.value}")

            # Fetch existing relationships
            await allow_web_rule.source_addresses.fetch()
            await allow_web_rule.destination_addresses.fetch()
            await allow_web_rule.services.fetch()
            await allow_web_rule.applications.fetch()

            # Get the address groups
            try:
                internet_group = await client.get(
                    kind="SecurityAddressGroup", name__value="internet"
                )
            except Exception as e:
                print(f"  ⚠️  Error getting internet group: {e}")
                internet_group = None

            try:
                web_servers_group = await client.get(
                    kind="SecurityAddressGroup", name__value="web-servers"
                )
            except Exception as e:
                print(f"  ⚠️  Error getting web-servers group: {e}")
                web_servers_group = None

            # Get the service group
            try:
                web_services_group = await client.get(
                    kind="SecurityServiceGroup", name__value="web-services"
                )
            except Exception as e:
                print(f"  ⚠️  Error getting web-services group: {e}")
                web_services_group = None

            # Get the application
            try:
                web_browsing_app = await client.get(
                    kind="SecurityApplication", name__value="web-browsing"
                )
            except Exception as e:
                print(f"  ⚠️  Error getting web-browsing application: {e}")
                web_browsing_app = None

            if internet_group:
                allow_web_rule.source_addresses.add(internet_group.id)
            if web_servers_group:
                allow_web_rule.destination_addresses.add(web_servers_group.id)
            if web_services_group:
                allow_web_rule.services.add(web_services_group.id)
            if web_browsing_app:
                allow_web_rule.applications.add(web_browsing_app.id)

            await allow_web_rule.save()
            print(
                "  ✅ Added source addresses, destination addresses, services, and applications"
            )
        else:
            print("  ⚠️  Could not find allow-web-traffic rule")
    except Exception as e:
        print(f"  ⚠️  Error processing allow-web-traffic rule: {e}")


async def main() -> int:
    """Main entry point."""
    print("🚀 Populating Security Object Relationships\n")

    try:
        config = Config(
            address=os.getenv("INFRAHUB_ADDRESS", "http://localhost:8000"),
            api_token=os.getenv(
                "INFRAHUB_API_TOKEN", "06438eb2-8019-4776-878c-0941b1f1d1ec"
            ),
        )
        client = InfrahubClient(config=config)

        await populate_address_groups(client)
        await populate_service_groups(client)
        await populate_firewall_policies(client)
        await populate_policy_rules(client)

        print("\n✅ All relationships populated successfully!\n")
        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
