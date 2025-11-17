from infrahub_sdk.transforms import InfrahubTransform


class TopologyCabling(InfrahubTransform):
    query = "topology_cabling"

    async def transform(self, data: dict) -> str:
        # Create a list to hold CSV rows
        csv_rows = []

        # Add CSV header with cable details
        csv_rows.append(
            "Source Device,Source Interface,Remote Device,Remote Interface,Cable Type,Cable Status,Cable Color,Cable Label"
        )

        seen_connections = set()  # Track connections we've already processed

        for device in data["TopologyDataCenter"]["edges"][0]["node"]["devices"][
            "edges"
        ]:
            source_device = device["node"]["name"]["value"]

            for interface in device["node"]["interfaces"]["edges"]:
                cable = interface["node"].get("connector", {}).get("node")
                if not cable:
                    continue

                source_interface = interface["node"]["name"]["value"]

                # Get cable details
                cable_type = cable.get("cable_type", {}).get("value", "")
                cable_status = cable.get("status", {}).get("value", "")
                cable_color = cable.get("color", {}).get("value", "")
                cable_label = cable.get("label", {}).get("value", "")

                # Get connected endpoints
                endpoints = cable.get("connected_endpoints", {}).get("edges", [])
                if not endpoints:
                    continue

                # Find the remote endpoint (the one that's not the current interface)
                remote_endpoint = None
                for endpoint in endpoints:
                    endpoint_node = endpoint.get("node", {})
                    endpoint_device = endpoint_node.get("device", {}).get("node", {}).get("name", {}).get("value")
                    endpoint_interface = endpoint_node.get("name", {}).get("value")

                    # Skip if this is the current interface
                    if endpoint_device == source_device and endpoint_interface == source_interface:
                        continue

                    remote_endpoint = endpoint_node
                    break

                if not remote_endpoint:
                    continue

                remote_device = remote_endpoint.get("device", {}).get("node", {}).get("name", {}).get("value")
                remote_interface = remote_endpoint.get("name", {}).get("value")

                if not remote_device or not remote_interface:
                    continue

                # Create a unique identifier for this connection (sorted to handle duplicates)
                connection_key = tuple(
                    sorted(
                        [
                            (source_device, source_interface),
                            (remote_device, remote_interface),
                        ]
                    )
                )

                # Skip if we've seen this connection already
                if connection_key in seen_connections:
                    continue

                # Add to our tracking set
                seen_connections.add(connection_key)

                # Format this row and add to our list
                # Escape any commas in field values with quotes
                row = [
                    source_device,
                    source_interface,
                    remote_device,
                    remote_interface,
                    cable_type,
                    cable_status,
                    cable_color,
                    cable_label,
                ]
                escaped_row = [f'"{field}"' if "," in str(field) else str(field) for field in row]
                csv_rows.append(",".join(escaped_row))

        # Join all rows with newlines to create CSV string
        csv_data = "\n".join(csv_rows)

        return csv_data
