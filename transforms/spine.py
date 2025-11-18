from typing import Any

from infrahub_sdk.transforms import InfrahubTransform
from jinja2 import Environment, FileSystemLoader
from netutils.utils import jinja2_convenience_function

from .common import (
    get_bgp_profile,
    get_data,
    get_interface_roles,
    get_loopbacks,
    get_ospf,
)


class Spine(InfrahubTransform):
    query = "spine_config"

    async def transform(self, data: Any) -> Any:
        data = get_data(data)

        # Get platform information
        platform = data["device_type"]["platform"]["netmiko_device_type"]

        # Set up Jinja2 environment to load templates from the role subfolder
        template_path = f"{self.root_directory}/templates/configs/spines"
        env = Environment(
            loader=FileSystemLoader(template_path),
            autoescape=False,  # Disable autoescape for device configs (not HTML)
        )
        env.filters.update(jinja2_convenience_function())

        # Select the template for spine devices based on platform
        template_name = f"{platform}.j2"

        # Render the template with enhanced data
        template = env.get_template(template_name)

        bgp_profiles = get_bgp_profile(data.get("device_services"))
        ospf_configs = get_ospf(data.get("device_services"))

        # Extract first OSPF config or use empty dict
        ospf = ospf_configs[0] if ospf_configs else {}

        # Create both flattened BGP dict (for Arista/Juniper templates)
        # and pass original bgp_profiles list (for Cisco template)
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
            "bgp": bgp,  # Flattened dict for Arista/Juniper/SONiC templates
            "bgp_profiles": bgp_profiles,  # Original list for Cisco template
            "ospf": ospf,
            "interface_roles": get_interface_roles(data.get("interfaces")),
            "loopbacks": get_loopbacks(data.get("interfaces")),
        }

        return template.render(**config)
