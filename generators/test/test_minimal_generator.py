"""
Minimal generator to reproduce object template duplicate interface bug.

This generator creates a single device using an object template and then
attempts to query one of its interfaces, demonstrating the duplicate
interface creation bug.
"""
from typing import Any

from infrahub_sdk.generator import InfrahubGenerator


class MinimalTestGenerator(InfrahubGenerator):
    """Minimal generator to reproduce duplicate interface bug."""

    async def generate(self, data: dict[str, Any]) -> None:
        """
        Create a single device with object template and check for duplicates.

        Expected behavior: Device should have 2 interfaces (eth0, eth1)
        Actual behavior: Device has 4 interfaces (eth0, eth0, eth1, eth1)
        """
        self.logger.info("=" * 60)
        self.logger.info("MINIMAL REPRODUCTION TEST FOR DUPLICATE INTERFACE BUG")
        self.logger.info("=" * 60)

        # Get topology data
        topology = data["TopologyDataCenter"]["edges"][0]["node"]
        topology_name = topology["name"]["value"]

        self.logger.info(f"Creating test device for topology: {topology_name}")

        # Create a single device with object template
        device_name = f"{topology_name.lower()}-device-01"

        self.logger.info(f"Step 1: Creating device '{device_name}' with object template...")

        device = await self.client.create(
            kind="DcimPhysicalDevice",
            data={
                "name": device_name,
                "object_template": ["TEST-DEVICE-TEMPLATE"],
                "device_type": "TEST-DEVICE-TYPE",
                "platform": "TestOS",
                "location": topology["location"]["node"]["id"],
                "status": "active",
                "role": "leaf",
            },
            branch=self.branch,
        )

        # Save the device (this is where templates are applied)
        await device.save(allow_upsert=False)

        self.logger.info(f"✓ Device created with ID: {device.id}")

        # Query all interfaces for this device
        self.logger.info(f"\nStep 2: Querying interfaces for device '{device_name}'...")

        interfaces = await self.client.filters(
            kind="DcimPhysicalInterface",
            device__name__value=device_name,
            branch=self.branch,
        )

        interface_count = len(interfaces)
        self.logger.info(f"Total interfaces found: {interface_count}")

        # Group by name to show duplicates
        interface_names: dict[str, int] = {}
        for intf in interfaces:
            name = intf.name.value
            interface_names[name] = interface_names.get(name, 0) + 1

        self.logger.info("\nInterface breakdown:")
        for name, count in sorted(interface_names.items()):
            status = "✓ OK" if count == 1 else f"✗ DUPLICATE ({count} copies)"
            self.logger.info(f"  {name}: {status}")

        # Determine test result
        expected_count = 2
        has_duplicates = any(count > 1 for count in interface_names.values())

        self.logger.info("\n" + "=" * 60)
        if interface_count == expected_count and not has_duplicates:
            self.logger.info("RESULT: ✓ PASS - No duplicates detected")
        else:
            self.logger.error(f"RESULT: ✗ FAIL - Expected {expected_count} interfaces, found {interface_count}")
            self.logger.error(f"        Duplicate interfaces detected: {has_duplicates}")

        self.logger.info("=" * 60)

        # Now try to get a specific interface (this will fail if duplicates exist)
        if has_duplicates:
            self.logger.info(f"\nStep 3: Attempting to get interface 'eth0' (will fail with duplicates)...")
            try:
                eth0 = await self.client.get(
                    kind="DcimPhysicalInterface",
                    device__name__value=device_name,
                    name__value="eth0",
                    branch=self.branch,
                )
                self.logger.info(f"✓ Successfully retrieved eth0: {eth0.id}")
            except IndexError as e:
                self.logger.error(f"✗ FAILED: {e}")
                self.logger.error("This is the bug - client.get() fails when duplicates exist")
                raise
