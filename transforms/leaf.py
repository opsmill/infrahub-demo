from typing import Any

from infrahub_sdk.transforms import InfrahubTransform
from jinja2 import Environment, FileSystemLoader

from .common import (
    get_bgp_profile,
    get_data,
    get_interface_roles,
    get_loopbacks,
    get_ospf,
    get_vlans,
)


class Leaf(InfrahubTransform):
    query = "leaf_config"

    async def transform(self, data: Any) -> Any:
        data = get_data(data)

        # Get platform information
        platform = data["device_type"]["platform"]["netmiko_device_type"]

        # Set up Jinja2 environment to load templates from the role subfolder
        template_path = f"{self.root_directory}/templates/configs/leafs"
        env = Environment(
            loader=FileSystemLoader(template_path),
            autoescape=False,  # Disable autoescape for device configs (not HTML)
        )
        # Select the template for leaf devices based on platform
        template_name = f"{platform}.j2"

        # Render the template with enhanced data
        template = env.get_template(template_name)

        bgp_profiles = get_bgp_profile(data.get("device_services"))
        ospf_configs = get_ospf(data.get("device_services"))

        # Extract first OSPF config or use empty dict
        ospf = ospf_configs[0] if ospf_configs else {}

        # Restructure BGP data for template
        # Template expects: bgp.local_as, bgp.router_id, bgp.neighbors
        bgp = {}
        if bgp_profiles:
            # Get common BGP settings from first profile
            first_profile = bgp_profiles[0]
            # Extract router_id address and strip CIDR notation if present
            router_id = first_profile.get("router_id", {}).get("address", "")
            if router_id and "/" in router_id:
                router_id = router_id.split("/")[0]
            bgp = {
                "local_as": first_profile.get("local_as", {}).get("asn", ""),
                "router_id": router_id,
                "neighbors": [],
            }
            # Collect all neighbors from all profiles
            for profile in bgp_profiles:
                for session in profile.get("sessions", []):
                    neighbor = {
                        "name": session.get("name", ""),
                        "remote_ip": session.get("remote_ip", {}).get("address", ""),
                        "remote_as": session.get("remote_as", {}).get("asn", ""),
                    }
                    bgp["neighbors"].append(neighbor)

        config = {
            "hostname": data.get("name"),
            "bgp": bgp,
            "ospf": ospf,
            "interfaces": get_interface_roles(data.get("interfaces")),
            "vlans": get_vlans(data.get("interfaces")),
            "loopbacks": get_loopbacks(data.get("interfaces")),
        }

        return template.render(**config)
