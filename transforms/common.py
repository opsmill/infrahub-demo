"""
Common utility functions for Infrahub topology generators.

This module provides data cleaning utilities to normalize and extract values
from nested data structures returned by Infrahub APIs.
"""

import html
from collections import defaultdict
from typing import Any

from netutils.interface import sort_interface_list


def clean_data(data: Any) -> Any:
    """
    Recursively normalize Infrahub API data by extracting values from nested dictionaries and lists.
    """
    # Handle dictionaries
    if isinstance(data, dict):
        dict_result = {}
        for key, value in data.items():
            if isinstance(value, dict):
                # Handle special cases with single keys
                keys = set(value.keys())
                if keys == {"value"}:
                    dict_result[key] = value["value"]  # This handles None values too
                elif keys == {"edges"} and not value["edges"]:
                    dict_result[key] = []
                # Handle nested structures
                elif "node" in value:
                    dict_result[key] = clean_data(value["node"])
                elif "edges" in value:
                    dict_result[key] = clean_data(value["edges"])
                # Process any other dictionaries
                else:
                    dict_result[key] = clean_data(value)
            elif "__" in key:
                dict_result[key.replace("__", "")] = value
            else:
                dict_result[key] = clean_data(value)
        return dict_result

    # Handle lists
    if isinstance(data, list):
        return [clean_data(item.get("node", item)) for item in data]

    # Return primitives unchanged
    return data


def get_data(data: Any) -> Any:
    """
    Extracts the relevant data from the input.
    Returns the first value from the cleaned data dictionary.
    """
    cleaned_data = clean_data(data)
    if isinstance(cleaned_data, dict) and cleaned_data:
        first_key = next(iter(cleaned_data))
        first_value = cleaned_data[first_key]
        if isinstance(first_value, list) and first_value:
            return first_value[0]
        return first_value
    else:
        raise ValueError("clean_data() did not return a non-empty dictionary")


def get_bgp_profile(device_services: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Groups BGP sessions by peer group and returns a list of peer group dicts in the desired structure.
    """
    unique_keys = {"name", "remote_ip", "remote_as"}
    peer_groups = defaultdict(list)
    for service in device_services:
        if service.get("typename") == "ServiceBGP":
            peer_group_name = service.get("peer_group", {}).get("name", "unknown")
            peer_groups[peer_group_name].append(service)

    grouped = []
    for sessions in peer_groups.values():
        if not sessions:
            continue
        base_settings = {
            k: v
            for k, v in sessions[0].items()
            if k not in unique_keys and k != "peer_group"
        }
        for session in sessions[1:]:
            keys_to_remove = []
            for k in base_settings:
                if session.get(k) != base_settings[k]:
                    keys_to_remove.append(k)
            for k in keys_to_remove:
                base_settings.pop(k)
        session_entries = []
        for session in sessions:
            entry = {k: v for k, v in session.items() if k in unique_keys}
            session_entries.append(entry)
        if sessions[0].get("peer_group"):
            base_settings["profile"] = sessions[0]["peer_group"].get("name")
        base_settings["sessions"] = session_entries
        grouped.append(base_settings)  # Store as list element

    return grouped


def get_ospf(device_services: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Extract OSPF configuration information.
    """
    ospf_configs: list[dict[str, Any]] = []

    for service in device_services:
        if service.get("typename") == "ServiceOSPF":
            # Extract router_id address and strip CIDR notation if present
            router_id = service.get("router_id", {}).get("address", "")
            if router_id and "/" in router_id:
                router_id = router_id.split("/")[0]

            ospf_config = {
                "process_id": service.get("process_id", 1),
                "router_id": router_id,
                "area": service.get("area", {}).get("area"),
                "reference_bandwidth": service.get("reference_bandwidth", 10000),
            }
            ospf_configs.append(ospf_config)

    return ospf_configs


def get_vlans(data: list) -> list[dict[str, Any]]:
    """
    Extracts VLAN information from the input data.
    Returns a list of dicts with only vlan_id and name, unique per (vlan_id, name).
    """
    return [
        {"vlan_id": vlan_id, "name": vlan_name}
        for vlan_id, vlan_name in {
            (segment.get("vlan_id"), segment.get("name"))
            for interface in data
            for segment in interface.get("interface_services", [])
            if segment.get("typename") == "ServiceNetworkSegment"
        }
    ]


def get_loopbacks(data: list) -> dict[str, str]:
    """
    Extracts loopback interfaces and their primary IP addresses.
    Returns a dictionary mapping loopback interface names to IP addresses (without mask).
    Example: {"loopback0": "10.0.0.1", "loopback1": "10.0.0.2"}
    """
    loopbacks = {}
    for iface in data:
        name = iface.get("name", "")
        if not name:
            continue

        name_lower = name.lower()
        role = iface.get("role", "").lower()

        # Check if this is a loopback interface by role or name
        is_loopback = (
            role == "loopback"
            or "loopback" in name_lower
            or (len(name_lower) >= 2 and name_lower[:2] == "lo")
        )

        if is_loopback:
            ip_addresses = iface.get("ip_addresses", [])
            if ip_addresses:
                # Get the first IP address and strip the mask if present
                address = ip_addresses[0].get("address", "")
                # Remove CIDR notation for router-id compatibility
                if "/" in address:
                    address = address.split("/")[0]
                loopbacks[name_lower] = address

    return loopbacks


def get_interfaces(data: list) -> list[dict[str, Any]]:
    """
    Returns a list of interface dictionaries sorted by interface name.
    Only includes 'ospf' key if OSPF area is present.
    Includes IP addresses, description, status, role, and other interface data.
    """
    sorted_names = sort_interface_list(
        [iface.get("name") for iface in data if iface.get("name")]
    )
    name_to_interface = {}
    for iface in data:
        name = iface.get("name")
        if not name:
            continue

        vlans = [
            s.get("vlan_id")
            for s in iface.get("interface_services", [])
            if s.get("typename") == "ServiceNetworkSegment"
        ]
        ospf_areas = [
            s.get("area", {}).get("area")
            for s in iface.get("interface_services", [])
            if s.get("typename") == "ServiceOSPF"
        ]

        # Decode HTML entities in description (e.g., &gt; -> >)
        description = iface.get("description")
        if description:
            description = html.unescape(description)

        iface_dict = {
            "name": name,
            "vlans": vlans,
            "description": description,
            "status": iface.get("status"),
            "role": iface.get("role"),
            "interface_type": iface.get("interface_type"),
            "mtu": iface.get("mtu"),
            "ip_addresses": iface.get("ip_addresses", []),
        }

        if ospf_areas:
            iface_dict["ospf"] = {"area": ospf_areas[0]}

        name_to_interface[name] = iface_dict

    return [
        name_to_interface[name] for name in sorted_names if name in name_to_interface
    ]


def get_interface_roles(data: list) -> dict[str, list[dict[str, Any]]]:
    """
    Organizes interfaces by their role for template consumption.
    Returns a dictionary with keys like 'loopback', 'uplink', 'downlink', 'all_downlink', 'all_physical'.
    Each value is a list of interface dictionaries with ip_address (first IP with mask).
    """
    # First get all interfaces using existing function
    all_interfaces = get_interfaces(data)

    # Organize by role
    roles: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for iface in all_interfaces:
        role = (iface.get("role") or "").lower()
        name_lower = iface.get("name", "").lower()

        # Create interface dict with ip_address (first IP with mask)
        iface_copy = iface.copy()
        if iface.get("ip_addresses"):
            iface_copy["ip_address"] = iface["ip_addresses"][0].get("address", "")
        else:
            iface_copy["ip_address"] = ""

        # Categorize by role
        if (
            role == "loopback"
            or "loopback" in name_lower
            or name_lower.startswith("lo")
        ):
            roles["loopback"].append(iface_copy)
        elif role in ("uplink", "spine"):
            roles["uplink"].append(iface_copy)
        elif role in ("downlink", "leaf"):
            roles["downlink"].append(iface_copy)
        elif role in ("customer", "access"):
            roles["customer"].append(iface_copy)
        else:
            # Physical interfaces (non-loopback)
            if not (role == "loopback" or "loopback" in name_lower):
                roles["other"].append(iface_copy)

    # Create aggregate lists
    roles["all_downlink"] = roles["downlink"] + roles["customer"]
    roles["all_physical"] = (
        roles["uplink"] + roles["downlink"] + roles["customer"] + roles["other"]
    )

    return dict(roles)
