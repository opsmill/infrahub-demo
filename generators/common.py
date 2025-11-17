import logging
import re
from typing import Any

from infrahub_sdk import InfrahubClient
from infrahub_sdk.exceptions import GraphQLError, ValidationError
from infrahub_sdk.protocols import CoreIPAddressPool
from netutils.interface import sort_interface_list

from .schema_protocols import DcimConsoleInterface, InterfacePhysical

# Range expansion pattern from infrahub_sdk
RANGE_PATTERN = re.compile(r"(\[[\w,-]*[-,][\w,-]*\])")


def expand_interface_range(interface_name: str) -> list[str]:
    """
    Expand interface name with bracket notation into individual interfaces.

    Examples:
        "Ethernet[1-3]" -> ["Ethernet1", "Ethernet2", "Ethernet3"]
        "Ethernet5" -> ["Ethernet5"]
    """
    # Check if interface name has bracket notation
    if not RANGE_PATTERN.search(interface_name):
        return [interface_name]

    # Simple range expansion for interfaces like Ethernet[1-48]
    # Extract the pattern
    match = RANGE_PATTERN.search(interface_name)
    if not match:
        return [interface_name]

    bracket_content = match.group(1)[1:-1]  # Remove [ and ]
    prefix = interface_name[:match.start()]
    suffix = interface_name[match.end():]

    # Handle numeric ranges like [1-48] or [1,3,5]
    expanded = []
    for part in bracket_content.split(','):
        if '-' in part:
            start, end = part.split('-')
            if start.isdigit() and end.isdigit():
                for i in range(int(start), int(end) + 1):
                    expanded.append(f"{prefix}{i}{suffix}")
            else:
                # Can't parse, return as-is
                return [interface_name]
        elif part.isdigit():
            expanded.append(f"{prefix}{part}{suffix}")
        else:
            # Can't parse, return as-is
            return [interface_name]

    return expanded if expanded else [interface_name]


def safe_sort_interface_list(interface_names: list[str]) -> list[str]:
    """
    Safely sort interface names using netutils, falling back to alphabetical sorting.

    Args:
        interface_names: List of interface names to sort

    Returns:
        Sorted list of interface names
    """
    try:
        return sort_interface_list(interface_names)
    except (ValueError, TypeError):
        # If netutils can't parse interface names (e.g., special characters),
        # fall back to simple alphabetical sorting
        return sorted(interface_names)


def clean_data(data: Any) -> Any:
    """
    Recursively transforms the input data by extracting 'value', 'node', or 'edges' from dictionaries.

    Args:
        data: The input data to clean.

    Returns:
        The cleaned data with extracted values.
    """
    if isinstance(data, dict):
        dict_result = {}
        for key, value in data.items():
            if isinstance(value, dict):
                if value.get("value"):
                    dict_result[key] = value["value"]
                elif value.get("node"):
                    dict_result[key] = clean_data(value["node"])
                elif value.get("edges"):
                    dict_result[key] = clean_data(value["edges"])
                elif not value.get("value"):
                    dict_result[key] = None
                else:
                    dict_result[key] = clean_data(value)
            elif "__" in key:
                dict_result[key.replace("__", "")] = value
            else:
                dict_result[key] = clean_data(value)
        return dict_result
    if isinstance(data, list):
        list_result = []
        for item in data:
            if isinstance(item, dict) and item.get("node", None) is not None:
                list_result.append(clean_data(item["node"]))
                continue
            list_result.append(clean_data(item))
        return list_result
    return data


class TopologyCreator:
    """
    Handles the creation of topology elements in Infrahub.
    """

    def __init__(
        self, client: InfrahubClient, log: logging.Logger, branch: str, data: dict
    ):
        """
        Initialize the TopologyCreator.

        Args:
            client: InfrahubClient instance.
            log: Logger instance.
            branch: Branch name.
            data: Topology data dictionary.
        """
        self.client = client
        self.log = log
        self.branch = branch
        self.data = data
        self.devices: list = []
        self.device_to_template: dict[str, str] = {}  # Map device name to template name

    async def _create_in_batch(
        self,
        kind: str,
        data_list: list,
        allow_upsert: bool = True,
    ) -> None:
        """
        Create objects of a specific kind and store in local store.

        Args:
            kind: The kind of object to create.
            data_list: List of data dictionaries for creation.
            allow_upsert: Whether to allow idempotent upsert operations (default: True).
        """
        batch = await self.client.create_batch()
        for data in data_list:
            try:
                obj = await self.client.create(
                    kind=kind, data=data.get("payload"), branch=self.branch
                )
                batch.add(task=obj.save, allow_upsert=allow_upsert, node=obj)
                if data.get("store_key"):
                    self.client.store.set(
                        key=data.get("store_key"), node=obj, branch=self.branch
                    )
            except GraphQLError as exc:
                self.log.debug(f"- Creation failed due to {exc}")
        try:
            async for node, _ in batch.execute():
                object_reference = (
                    " ".join(node.hfid) if node.hfid else node.display_label
                )
                self.log.info(
                    f"- Created [{node.get_kind()}] {object_reference}"
                    if object_reference
                    else f"- Created [{node.get_kind()}]"
                )
        except ValidationError as exc:
            self.log.debug(f"- Creation failed due to {exc}")

    async def _create(self, kind: str, data: dict) -> None:
        """
        Create an object of a specific kind and store in local store.

        Args:
            kind: The kind of object to create.
            data: The data dictionary for creation.
        """
        try:
            obj = await self.client.create(
                kind=kind, data=data.get("payload"), branch=self.branch
            )
            await obj.save(allow_upsert=True)
            object_reference = " ".join(obj.hfid) if obj.hfid else obj.display_label
            self.log.info(
                f"- Created [{kind}] {object_reference}"
                if object_reference
                else f"- Created [{kind}]"
            )
            if data.get("store_key"):
                self.client.store.set(
                    key=data.get("store_key"), node=obj, branch=self.branch
                )
                self.log.info(f"- Stored {kind} in store with key='{data.get('store_key')}' on branch='{self.branch}'")
        except (GraphQLError, ValidationError) as exc:
            self.log.error(f"- Creation failed for {kind}: {exc}")
            raise
        except Exception as exc:
            self.log.error(f"- Unexpected error creating {kind}: {type(exc).__name__}: {exc}")
            raise

    async def load_data(self) -> None:
        """Load data and store in cache."""
        # Expand interface ranges in templates
        expanded_templates = {}
        for item in self.data["design"]["elements"]:
            template_name = item["template"]["template_name"]
            template_interfaces = item["template"]["interfaces"]

            # Expand each interface that has range notation
            expanded_interfaces = []
            for iface in template_interfaces:
                iface_name = iface.get("name")
                if iface_name and RANGE_PATTERN.search(iface_name):
                    # Expand the range
                    for expanded_name in expand_interface_range(iface_name):
                        expanded_iface = iface.copy()
                        expanded_iface["name"] = expanded_name
                        expanded_interfaces.append(expanded_iface)
                else:
                    expanded_interfaces.append(iface)

            expanded_templates[template_name] = expanded_interfaces

        self.data.update({"templates": expanded_templates})

        roles = list(
            set(f"{item['role']}s" for item in self.data["design"]["elements"])
        )
        manufacturers = list(
            set(
                f"{item['device_type']['manufacturer']['name'].lower().replace(' ', '_')}_{item['role']}"
                for item in self.data["design"]["elements"]
            )
        )

        # Add juniper_firewall group if any firewall roles are present
        firewall_roles = {"dc_firewall", "edge_firewall"}
        if any(
            item["role"] in firewall_roles for item in self.data["design"]["elements"]
        ):
            roles.append("juniper_firewall")

        await self.client.filters(
            kind="CoreStandardGroup",
            name__values=roles + manufacturers,
            branch=self.branch,
            populate_store=True,
        )
        # get the device templates
        await self.client.filters(
            kind="CoreObjectTemplate",
            template_name__values=list(
                set(
                    item["template"]["template_name"]
                    for item in self.data["design"]["elements"]
                )
            ),
            branch=self.branch,
            populate_store=True,
        )

    async def create_site(self) -> None:
        """Create site."""
        site_name = self.data.get('name')
        self.log.info(f"Create site {site_name}")

        # Validate data structure
        if not self.data.get("location"):
            raise ValueError(f"No location found in topology data for {site_name}")
        if not self.data["location"].get("id"):
            raise ValueError(f"Location has no ID in topology data for {site_name}")

        self.log.info(f"Creating LocationBuilding '{site_name}' with parent location ID: {self.data['location']['id']}")

        await self._create(
            kind="LocationBuilding",
            data={
                "payload": {
                    "name": self.data["name"],
                    "shortname": self.data["name"],
                    "parent": self.data["location"]["id"],
                },
                "store_key": self.data["name"],
            },
        )

    async def create_location_hierarchy(self) -> None:
        """Create LocationPod and LocationRow for the datacenter."""
        site_name = self.data.get('name')
        self.log.info(f"Creating location hierarchy for {site_name}")

        # Get the building we just created
        building = self.client.store.get(
            kind="LocationBuilding",
            key=site_name,
            branch=self.branch,
        )

        # Create Pod-1
        await self._create(
            kind="LocationPod",
            data={
                "payload": {
                    "name": "Pod-1",
                    "shortname": "Pod-1",
                    "parent": building.id,
                },
                "store_key": f"{site_name}-Pod-1",
            },
        )

        # Get the pod we just created
        pod = self.client.store.get(
            kind="LocationPod",
            key=f"{site_name}-Pod-1",
            branch=self.branch,
        )

        # Create Row-1
        await self._create(
            kind="LocationRow",
            data={
                "payload": {
                    "name": "Row-1",
                    "shortname": "Row-1",
                    "parent": pod.id,
                },
                "store_key": f"{site_name}-Row-1",
            },
        )

    async def create_racks(self) -> None:
        """Create racks based on the number of leaf devices."""
        site_name = self.data.get('name')

        # Count leaf devices from design elements
        num_leafs = sum(
            device["quantity"]
            for device in self.data["design"]["elements"]
            if device["role"] == "leaf"
        )

        self.log.info(f"Creating {num_leafs} racks for {site_name}")

        # Get the row we just created
        row = self.client.store.get(
            kind="LocationRow",
            key=f"{site_name}-Row-1",
            branch=self.branch,
        )

        # Create racks
        rack_data_list = []
        for i in range(1, num_leafs + 1):
            rack_name = f"Rack-{i}"
            rack_data_list.append({
                "payload": {
                    "name": rack_name,
                    "shortname": rack_name,
                    "parent": row.id,
                },
                "store_key": f"{site_name}-{rack_name}",
            })

        await self._create_in_batch(
            kind="LocationRack",
            data_list=rack_data_list,
        )

    async def assign_devices_to_racks(self) -> None:
        """Assign devices to racks with proper positioning."""
        site_name = self.data.get('name')
        self.log.info(f"Assigning devices to racks for {site_name}")

        # Group devices by role
        leaf_devices = [d for d in self.devices if d.role.value == "leaf"]
        border_leaf_devices = [d for d in self.devices if d.role.value == "border_leaf"]
        spine_devices = [d for d in self.devices if d.role.value == "spine"]
        console_devices = [d for d in self.devices if "console" in d.role.value.lower()]
        oob_devices = [d for d in self.devices if "oob" in d.role.value.lower()]

        # Calculate total rack count and middle racks
        total_racks = len(leaf_devices)

        if total_racks == 0:
            self.log.warning("No leaf devices found, skipping rack assignment")
            return

        # Calculate middle rack positions for devices that go in the middle
        # (spines, border_leafs, console, oob)
        middle_device_count = max(
            len(spine_devices),
            len(border_leaf_devices) + len(console_devices) + len(oob_devices)
        )
        middle_start = (total_racks // 2) - (middle_device_count // 2)
        middle_racks = list(range(middle_start + 1, middle_start + middle_device_count + 1))

        # Track rack occupancy (rack_number -> list of (device, position, height))
        rack_occupancy: dict[int, list[tuple[Any, int, int]]] = {
            i: [] for i in range(1, total_racks + 1)
        }

        # Helper function to extract device number from name
        def get_device_number(device_name: str) -> int:
            """Extract device number from name like 'dc-3-leaf-01' -> 1"""
            parts = device_name.split("-")
            return int(parts[-1])

        # Helper function to get device height
        async def get_device_height(device: Any) -> int:
            """Get device height from device_type"""
            if hasattr(device, "device_type"):
                device_type = device.device_type
                if hasattr(device_type, "peers") and device_type.peers:
                    device_type_obj = device_type.peers[0]
                    if hasattr(device_type_obj, "height"):
                        height = device_type_obj.height
                        return height.value if hasattr(height, "value") else int(height)
            return 1  # Default to 1U

        # Assign leaf devices to racks
        for device in leaf_devices:
            device_num = get_device_number(device.name.value)
            rack_num = device_num

            if rack_num > total_racks:
                self.log.warning(f"Device {device.name.value} number ({device_num}) exceeds rack count ({total_racks}), skipping")
                continue

            device_height = await get_device_height(device)
            position = 42 - (device_height - 1)  # Top of rack
            rack_occupancy[rack_num].append((device, position, device_height))

        # Assign border leaf devices to middle racks
        border_leaf_rack_idx = 0
        for device in border_leaf_devices:
            if border_leaf_rack_idx >= len(middle_racks):
                self.log.warning(f"Not enough middle racks for border leaf {device.name.value}")
                break

            rack_num = middle_racks[border_leaf_rack_idx]
            device_height = await get_device_height(device)

            # Find lowest occupied position in this rack
            if rack_occupancy[rack_num]:
                lowest_pos = min(pos for _, pos, _ in rack_occupancy[rack_num])
                position = lowest_pos - device_height
            else:
                position = 42 - (device_height - 1)

            rack_occupancy[rack_num].append((device, position, device_height))
            border_leaf_rack_idx += 1

        # Assign spine devices to middle racks
        spine_rack_idx = 0
        for device in spine_devices:
            if spine_rack_idx >= len(middle_racks):
                self.log.warning(f"Not enough middle racks for spine {device.name.value}")
                break

            rack_num = middle_racks[spine_rack_idx]
            device_height = await get_device_height(device)

            # Find lowest occupied position in this rack
            if rack_occupancy[rack_num]:
                lowest_pos = min(pos for _, pos, _ in rack_occupancy[rack_num])
                position = lowest_pos - device_height
            else:
                position = 42 - (device_height - 1)

            rack_occupancy[rack_num].append((device, position, device_height))
            spine_rack_idx += 1

        # Assign console devices to middle racks
        console_rack_idx = 0
        for device in console_devices:
            if console_rack_idx >= len(middle_racks):
                self.log.warning(f"Not enough middle racks for console device {device.name.value}")
                break

            rack_num = middle_racks[console_rack_idx]
            device_height = await get_device_height(device)

            # Find lowest occupied position in this rack
            if rack_occupancy[rack_num]:
                lowest_pos = min(pos for _, pos, _ in rack_occupancy[rack_num])
                position = lowest_pos - device_height
            else:
                position = 42 - (device_height - 1)

            rack_occupancy[rack_num].append((device, position, device_height))
            console_rack_idx += 1

        # Assign OOB devices to middle racks
        oob_rack_idx = 0
        for device in oob_devices:
            if oob_rack_idx >= len(middle_racks):
                self.log.warning(f"Not enough middle racks for OOB device {device.name.value}")
                break

            rack_num = middle_racks[oob_rack_idx]
            device_height = await get_device_height(device)

            # Find lowest occupied position in this rack
            if rack_occupancy[rack_num]:
                lowest_pos = min(pos for _, pos, _ in rack_occupancy[rack_num])
                position = lowest_pos - device_height
            else:
                position = 42 - (device_height - 1)

            rack_occupancy[rack_num].append((device, position, device_height))
            oob_rack_idx += 1

        # Now update all devices with their rack locations and positions
        batch = await self.client.create_batch()

        for rack_num, devices_in_rack in rack_occupancy.items():
            if not devices_in_rack:
                continue

            # Get rack object
            rack_name = f"Rack-{rack_num}"
            rack = self.client.store.get(
                kind="LocationRack",
                key=f"{site_name}-{rack_name}",
                branch=self.branch,
            )

            for device, position, height in devices_in_rack:
                # Infrahub handles bidirectional location relationships automatically
                device.location = rack.id
                device.position = position
                batch.add(task=device.save, allow_upsert=True, node=device)
                self.log.info(f"Assigned {device.name.value} to {rack_name} at position U{position} ({height}U device)")

        # Execute the batch update
        async for node, _ in batch.execute():
            self.log.info(f"- Updated location for [{node.get_kind()}] {node.name.value}")

    async def create_address_pools(self, subnets: list[dict]) -> None:
        """Create objects of a specific kind and store in local store.

        Args:
            subnets: List of subnet dicts with 'type' and 'prefix_id' keys.
                    Format: [{"type": "Management", "prefix_id": "subnet_id"}, ...]
        """
        self.log.info("Creating address pools")

        await self._create_in_batch(
            kind="CoreIPAddressPool",
            data_list=[
                {
                    "payload": {
                        "name": f"{self.data.get('name')}-{pool.get('type')}-pool",
                        "default_address_type": "IpamIPAddress",
                        "description": f"{pool.get('type')} IP Pool",
                        "ip_namespace": "default",
                        "resources": [pool.get("prefix_id")],
                    },
                    "store_key": f"{pool.get('type', '').lower()}_ip_pool",
                }
                for pool in subnets
            ],
            allow_upsert=True,
        )

    async def create_split_loopback_pools(self, technical_subnet_obj: Any) -> None:
        """Create separate IP address pools for underlay and VTEP loopbacks.

        Args:
            technical_subnet_obj: The technical subnet object to split
        """
        self.log.info("Creating split loopback pools for underlay and VTEP")

        # Split the technical subnet
        underlay_subnet_obj, vtep_subnet_obj = await self.split_technical_subnet(
            technical_subnet_obj
        )

        # Create address pools for both subnets
        subnets = [
            {
                "type": "Loopback",
                "prefix_id": underlay_subnet_obj.id,
            },
            {
                "type": "Loopback-VTEP",
                "prefix_id": vtep_subnet_obj.id,
            },
        ]

        await self.create_address_pools(subnets)

    async def split_technical_subnet(
        self, technical_subnet_obj: Any
    ) -> tuple[Any, Any]:
        """
        Split the technical subnet into two equal halves for underlay and VTEP loopbacks.

        Args:
            technical_subnet_obj: The technical subnet object to split

        Returns:
            tuple: (underlay_subnet_obj, vtep_subnet_obj)
        """
        import ipaddress

        # Get the prefix from the technical subnet
        original_prefix = ipaddress.ip_network(technical_subnet_obj.prefix.value)

        # Split into two equal subnets by adding 1 to the prefix length
        subnets = list(original_prefix.subnets(prefixlen_diff=1))

        if len(subnets) < 2:
            raise ValueError(f"Cannot split {original_prefix} - too small to split")

        underlay_subnet = subnets[0]  # First half for underlay
        vtep_subnet = subnets[1]  # Second half for VTEP

        self.log.info(f"Splitting {original_prefix} into:")
        self.log.info(f"  - Underlay: {underlay_subnet}")
        self.log.info(f"  - VTEP: {vtep_subnet}")

        # Create the underlay subnet object
        underlay_subnet_data = {
            "prefix": str(underlay_subnet),
            "status": "active",
            "role": "loopback",
            "description": f"{self.data.get('name')} Underlay Loopback Subnet",
        }

        underlay_subnet_obj = await self.client.create(
            kind="IpamPrefix", data=underlay_subnet_data, branch=self.branch
        )
        await underlay_subnet_obj.save(allow_upsert=True)

        # Create the VTEP subnet object
        vtep_subnet_data = {
            "prefix": str(vtep_subnet),
            "status": "active",
            "role": "loopback-vtep",
            "description": f"{self.data.get('name')} VTEP Loopback Subnet",
        }

        vtep_subnet_obj = await self.client.create(
            kind="IpamPrefix", data=vtep_subnet_data, branch=self.branch
        )
        await vtep_subnet_obj.save(allow_upsert=True)

        self.log.info(f"Created underlay subnet: {str(underlay_subnet)}")
        self.log.info(f"Created VTEP subnet: {str(vtep_subnet)}")

        return underlay_subnet_obj, vtep_subnet_obj

    async def create_L2_pool(self) -> None:
        """Create objects of a specific kind and store in local store."""
        await self._create(
            kind="CoreNumberPool",
            data={
                "payload": {
                    "name": f"{self.data.get('name')}-VLAN-POOL",
                    "description": f"{self.data.get('name')} VLAN Number Pool",
                    "node": "ServiceNetworkSegment",
                    "node_attribute": "vlan_id",
                    "start_range": 100,
                    "end_range": 4000,
                },
                # "store_key": f"{pool.get('type').lower()}_ip_pool",
            },
        )

    async def create_devices(self) -> None:
        self.log.info(f"Create devices for {self.data.get('name')}")
        # ... fetch device groups and templates logic ...
        physical_devices: list = []
        virtual_devices: list = []
        firewall_devices: list = []
        role_counters: dict = {}
        topology_name = self.data.get("name", "")

        # Populate the data_list with unique naming
        for device in self.data["design"]["elements"]:
            role = device["role"]

            # Initialize counter for this role if it doesn't exist
            role_counters.setdefault(role, 0)

            for i in range(1, device["quantity"] + 1):
                # Increment the counter for this role
                role_counters[role] += 1

                # Format the name string once per device
                name = f"{topology_name.lower()}-{role}-{str(role_counters[role]).zfill(2)}"

                # Track template name for this device
                template_name = device["template"]["template_name"]
                self.device_to_template[name] = template_name

                # Construct the payload once per device
                # Determine group name based on role
                if role in ["dc_firewall", "edge_firewall"]:
                    group_name = "juniper_firewall"
                else:
                    group_name = f"{role}s"

                payload = {
                    "name": name,
                    # Note: object_template removed - interfaces are created explicitly with expanded ranges
                    "device_type": device["device_type"]["id"],
                    "platform": device["device_type"]["platform"]["id"],
                    "status": "active",
                    "role": role,
                    "location": self.client.store.get(
                        kind="LocationBuilding",
                        key=topology_name,
                        branch=self.branch,
                    ).id,
                    "topology": self.data.get("id"),
                    "member_of_groups": [
                        self.client.store.get(
                            kind="CoreStandardGroup",
                            key=group_name,
                            branch=self.branch,
                        ).id,
                    ],
                    "primary_address": await self.client.allocate_next_ip_address(
                        resource_pool=self.client.store.get(
                            kind=CoreIPAddressPool, key="management_ip_pool", branch=self.branch
                        ),
                        identifier=f"{name}-management",
                        data={"description": f"{name} Management IP"},
                    ),
                }
                # Append the constructed dictionary to respective lists

                device_entry = {"payload": payload, "store_key": name}
                if "Virtual" in device["template"]["typename"]:
                    virtual_devices.append(device_entry)
                elif role in ["dc_firewall", "edge_firewall"]:
                    firewall_devices.append(device_entry)
                else:
                    physical_devices.append(device_entry)

        for kind, devices in [
            ("DcimDevice", physical_devices),
            ("DcimVirtualDevice", virtual_devices),
            ("SecurityFirewall", firewall_devices),
        ]:
            if devices:
                await self._create_in_batch(kind=kind, data_list=devices)

        # Get all devices that were created (DcimGenericDevice includes all subtypes)
        self.devices = []
        if "DcimGenericDevice" in self.client.store._branches[self.branch]._hfids:
            self.devices = [
                self.client.store.get_by_hfid(
                    key=f"DcimGenericDevice__{device[0]}",
                    branch=self.branch,
                )
                for device in self.client.store._branches[self.branch]
                ._hfids["DcimGenericDevice"]
                .keys()
            ]

        # Create interfaces for devices based on expanded templates
        await self.create_interfaces_from_templates()

    async def create_interfaces_from_templates(self) -> None:
        """Create interfaces for all devices based on their templates with expanded ranges."""
        self.log.info("Creating interfaces from templates with expanded ranges")

        for device in self.devices:
            template_name = self._get_device_template_name(device)
            if not template_name or template_name not in self.data["templates"]:
                self.log.warning(f"No template found for device {device.name.value if hasattr(device, 'name') else device.id}")
                continue

            # Get expanded interfaces from template
            template_interfaces = self.data["templates"][template_name]

            # Separate console interfaces from physical interfaces
            console_interface_data_list = []
            physical_interface_data_list = []

            for iface in template_interfaces:
                interface_data: dict[str, Any] = {
                    "payload": {
                        "name": iface["name"],
                        "device": device.id,
                        "status": "active",
                    },
                    "store_key": f"{device.name.value}-{iface['name']}" if hasattr(device, 'name') else None,
                }

                # Add role if present
                if iface.get("role"):
                    interface_data["payload"]["role"] = iface["role"]

                # Separate by role to create the correct interface type
                if iface.get("role") == "console":
                    # Console interfaces need port and speed attributes
                    interface_data["payload"]["port"] = iface.get("port", 0)
                    interface_data["payload"]["speed"] = iface.get("speed", 9600)
                    console_interface_data_list.append(interface_data)
                else:
                    physical_interface_data_list.append(interface_data)

            # Create console interfaces in batch
            if console_interface_data_list:
                await self._create_in_batch(
                    kind="DcimConsoleInterface",
                    data_list=console_interface_data_list,
                    allow_upsert=True,
                )
                self.log.info(f"Created {len(console_interface_data_list)} console interfaces for {device.name.value if hasattr(device, 'name') else device.id}")

            # Create physical interfaces in batch
            if physical_interface_data_list:
                await self._create_in_batch(
                    kind="InterfacePhysical",
                    data_list=physical_interface_data_list,
                    allow_upsert=True,
                )
                self.log.info(f"Created {len(physical_interface_data_list)} physical interfaces for {device.name.value if hasattr(device, 'name') else device.id}")

    def _get_device_template_name(self, device: Any) -> str | None:
        """
        Get the object template name from a device.

        Args:
            device: The device object

        Returns:
            The template name as a string, or None if not found
        """
        # First try to get from our internal mapping
        if hasattr(device, "name"):
            device_name = device.name.value if hasattr(device.name, "value") else str(device.name)
            if device_name in self.device_to_template:
                return self.device_to_template[device_name]

        # Fallback: try to get from object_template attribute (if it exists)
        try:
            if hasattr(device, "object_template"):
                template = device.object_template
                # It might be a relationship object
                if hasattr(template, "peers") and template.peers:
                    peer = template.peers[0]
                    if hasattr(peer, "hfid") and peer.hfid:
                        return (
                            peer.hfid[0] if isinstance(peer.hfid, list) else peer.hfid
                        )
        except (AttributeError, IndexError, TypeError):
            pass

        return None

    async def create_oob_connections(
        self,
        connection_type: str,
    ) -> None:
        """Create objects of a specific kind and store in local store."""
        batch = await self.client.create_batch()
        interfaces: dict = {}

        for device in self.devices:
            template_name = self._get_device_template_name(device)
            if template_name and template_name in self.data["templates"]:
                interfaces[device.name.value] = [
                    interface["name"]
                    for interface in self.data["templates"][template_name]
                    if interface["role"] == connection_type
                ]
            else:
                # Skip devices where we can't determine the template
                self.log.debug(
                    f"Skipping {device.name.value} - could not determine template"
                )
                interfaces[device.name.value] = []

        device_key = "oob" if connection_type == "management" else "console"
        sources = {
            key: safe_sort_interface_list(value)
            for key, value in interfaces.items()
            if device_key in key and value
        }

        destinations = {
            key: safe_sort_interface_list(value)
            for key, value in interfaces.items()
            if key not in sources and value
        }

        connections = [
            {
                "source": source_device,
                "target": destination_device,
                "source_interface": source_interfaces.pop(0),
                "destination_interface": destination_interfaces.pop(0),
            }
            for source_device, source_interfaces in sources.items()
            for destination_device, destination_interfaces in destinations.items()
            if source_interfaces and destination_interfaces  # Guard against empty lists
            and int(destination_device.split("-")[-1]) % 2
            == int(source_device.split("-")[-1]) % 2
        ]

        if connections:
            self.log.info(
                f"Create {connection_type} connections for {self.data.get('name')}"
            )

        for connection in connections:
            source_endpoint = await self.client.get(
                kind=(
                    InterfacePhysical
                    if connection_type == "management"
                    else DcimConsoleInterface
                ),
                name__value=connection["source_interface"],
                device__name__value=connection["source"],
            )
            target_endpoint = await self.client.get(
                kind=(
                    InterfacePhysical
                    if connection_type == "management"
                    else DcimConsoleInterface
                ),
                name__value=connection["destination_interface"],
                device__name__value=connection["target"],
            )

            source_endpoint.status.value = "active"
            source_endpoint.description.value = (
                f"Connection to {' -> '.join(target_endpoint.hfid or [])}"
            )
            # Infrahub handles bidirectional connector relationships automatically
            source_endpoint.connector = target_endpoint.id  # type: ignore[assignment]
            target_endpoint.status.value = "active"
            target_endpoint.description.value = (
                f"Connection to {' -> '.join(source_endpoint.hfid or [])}"
            )
            # Note: Don't set target_endpoint.connector - Infrahub creates bidirectional relationship automatically
            batch.add(
                task=source_endpoint.save, allow_upsert=True, node=source_endpoint
            )
            batch.add(
                task=target_endpoint.save, allow_upsert=True, node=target_endpoint
            )
        try:
            async for node, _ in batch.execute():
                self.log.info(
                    f"- Created [{node.get_kind()}] {node.description.value} from {' -> '.join(node.hfid)}"
                )

        except ValidationError as exc:
            self.log.debug(f"- Creation failed due to {exc}")

    async def create_loopback(
        self,
        loopback_name: str,
        pool_key: str = "loopback_ip_pool",
        interface_role: str = "loopback",
        loopback_type: str = "Loopback",
    ) -> None:
        """Create loopback interfaces with specified IP pool, role, and type

        Args:
            loopback_name: Name of the loopback interface (e.g., 'loopback0', 'loopback1')
            pool_key: Key for the IP address pool to use (default: 'loopback_ip_pool')
            interface_role: Interface role for the schema (default: 'loopback')
            loopback_type: Type description for logging and descriptions (default: 'Loopback')
        """
        self.log.info(f"Creating {loopback_name} {loopback_type.lower()} interfaces")
        await self._create_in_batch(
            kind="InterfaceVirtual",
            data_list=[
                {
                    "payload": {
                        "name": loopback_name,
                        "device": device.id,
                        "ip_addresses": [
                            await self.client.allocate_next_ip_address(
                                resource_pool=self.client.store.get(
                                    kind=CoreIPAddressPool, key=pool_key, branch=self.branch
                                ),
                                identifier=f"{device.name.value}-{loopback_name}",
                                data={
                                    "description": f"{device.name.value} {loopback_type} IP"
                                },
                            ),
                        ],
                        "role": interface_role,
                        "status": "active",
                        "description": f"{device.name.value} {loopback_name} {loopback_type} Interface",
                    },
                    "store_key": f"{device.name.value}-{loopback_name}",
                }
                for device in self.devices
                if device.role.value in ["spine", "leaf", "border_leaf", "edge"]
            ],
            allow_upsert=True,
        )
