from typing import Any

from infrahub_sdk.transforms import InfrahubTransform


class OpenConfigLeaf(InfrahubTransform):
    query = "openconfig_leaf_config"

    async def transform(self, data: Any) -> Any:
        response_payload: dict[str, Any] = {}
        response_payload["openconfig-interfaces:interfaces"] = {}
        response_payload["openconfig-interfaces:interfaces"]["interface"] = []

        # Extract device data
        device_node = data["DcimGenericDevice"]["edges"][0]["node"]

        # Process each interface
        for intf in device_node["interfaces"]["edges"]:
            intf_node = intf["node"]
            intf_name = intf_node["name"]["value"]

            # Build interface config
            # Determine if interface is enabled based on status
            status = intf_node.get("status", {}).get("value", "active")
            enabled = status == "active"

            intf_config = {
                "name": intf_name,
                "config": {
                    "name": intf_name,
                    "enabled": enabled,
                },
            }

            # Add description if available
            if intf_node.get("description") and intf_node["description"].get("value"):
                intf_config["config"]["description"] = intf_node["description"]["value"]

            # Add MTU if available
            if intf_node.get("mtu") and intf_node["mtu"].get("value"):
                intf_config["config"]["mtu"] = intf_node["mtu"]["value"]

            # Add IP addresses if available
            if intf_node.get("ip_addresses") and intf_node["ip_addresses"].get("edges"):
                intf_config["subinterfaces"] = {"subinterface": []}

                for idx, ip_edge in enumerate(intf_node["ip_addresses"]["edges"]):
                    ip_address_full = ip_edge["node"]["address"]["value"]
                    address, prefix_length = ip_address_full.split("/")

                    subintf_config = {
                        "index": idx,
                        "config": {"index": idx},
                        "openconfig-if-ip:ipv4": {
                            "addresses": {
                                "address": [
                                    {
                                        "ip": address,
                                        "config": {
                                            "ip": address,
                                            "prefix-length": int(prefix_length),
                                        },
                                    }
                                ]
                            },
                            "config": {"enabled": True},
                        },
                    }

                    intf_config["subinterfaces"]["subinterface"].append(subintf_config)

            response_payload["openconfig-interfaces:interfaces"]["interface"].append(
                intf_config
            )

        return response_payload
