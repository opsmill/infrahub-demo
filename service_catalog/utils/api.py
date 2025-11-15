"""Infrahub API client for the Service Catalog."""

from typing import Any, Dict, List, Optional

from infrahub_sdk import Config, InfrahubClientSync


class InfrahubAPIError(Exception):
    """Base exception for Infrahub API errors."""

    pass


class InfrahubConnectionError(InfrahubAPIError):
    """Exception raised when connection to Infrahub fails."""

    pass


class InfrahubHTTPError(InfrahubAPIError):
    """Exception raised for HTTP errors from Infrahub."""

    def __init__(self, message: str, status_code: int, response_text: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class InfrahubGraphQLError(InfrahubAPIError):
    """Exception raised for GraphQL errors from Infrahub."""

    def __init__(self, message: str, errors: List[Dict[str, Any]]):
        super().__init__(message)
        self.errors = errors


class InfrahubClient:
    """Client for interacting with the Infrahub API using the official SDK."""

    def __init__(self, base_url: str, api_token: Optional[str] = None, timeout: int = 30):
        """Initialize the Infrahub API client.

        Args:
            base_url: Base URL of the Infrahub instance (e.g., "http://localhost:8000")
            api_token: Optional API token for authentication (not currently used by SDK)
            timeout: Request timeout in seconds (default: 30)
        """
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout

        # Initialize the official Infrahub SDK client
        config = Config(timeout=timeout, api_token=api_token)
        self._client = InfrahubClientSync(address=base_url, config=config)

    def get_branches(self) -> List[Dict[str, Any]]:
        """Fetch all branches from Infrahub.

        Returns:
            List of branch dictionaries with keys: name, id, is_default, etc.

        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubAPIError: If API error occurs
        """
        try:
            branches_dict = self._client.branch.all()
            # Convert to list of dicts for compatibility
            branches = []
            for branch_name, branch_data in branches_dict.items():
                branches.append({
                    "name": branch_name,
                    "id": branch_data.id,
                    "is_default": branch_data.is_default,
                    "sync_with_git": branch_data.sync_with_git,
                })
            return branches
        except Exception as e:
            raise InfrahubConnectionError(f"Failed to fetch branches: {str(e)}")

    def get_objects(
        self, object_type: str, branch: str = "main"
    ) -> List[Dict[str, Any]]:
        """Fetch objects of a specific type from Infrahub.

        Args:
            object_type: Type of object to fetch (e.g., "TopologyDataCenter")
            branch: Branch name to query (default: "main")

        Returns:
            List of object dictionaries

        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubAPIError: If API error occurs
        """
        # Use specific methods for known types
        if object_type == "TopologyDataCenter":
            return self.get_datacenters(branch)
        elif object_type == "TopologyColocationCenter":
            return self.get_colocation_centers(branch)

        # Generic query for other types
        try:
            objects = self._client.filters(kind=object_type, branch=branch)
            # Convert SDK objects to dicts
            return [self._sdk_object_to_dict(obj) for obj in objects]
        except Exception as e:
            raise InfrahubAPIError(f"Failed to fetch {object_type}: {str(e)}")

    def get_datacenters(self, branch: str = "main") -> List[Dict[str, Any]]:
        """Fetch TopologyDataCenter objects with all required fields.

        Args:
            branch: Branch name to query (default: "main")

        Returns:
            List of datacenter dictionaries with full field structure

        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubAPIError: If API error occurs
        """
        try:
            datacenters = self._client.filters(
                kind="TopologyDataCenter",
                branch=branch,
                prefetch_relationships=True
            )

            result = []
            for dc in datacenters:
                dc_dict = {
                    "id": dc.id,
                    "name": {"value": getattr(dc.name, "value", None)},
                    "description": {"value": getattr(dc.description, "value", None) if hasattr(dc, "description") else None},
                    "strategy": {"value": getattr(dc.strategy, "value", None) if hasattr(dc, "strategy") else None},
                }

                # Add relationships if they exist
                if hasattr(dc, "location") and dc.location.peer:
                    dc_dict["location"] = {
                        "node": {
                            "id": dc.location.peer.id,
                            "display_label": str(dc.location.peer)
                        }
                    }

                if hasattr(dc, "design") and dc.design.peer:
                    design_peer = dc.design.peer
                    dc_dict["design"] = {
                        "node": {
                            "id": design_peer.id,
                            "name": {"value": getattr(design_peer.name, "value", None) if hasattr(design_peer, "name") else None}
                        }
                    }

                result.append(dc_dict)

            return result
        except Exception as e:
            raise InfrahubAPIError(f"Failed to fetch datacenters: {str(e)}")

    def get_colocation_centers(self, branch: str = "main") -> List[Dict[str, Any]]:
        """Fetch TopologyColocationCenter objects with all required fields.

        Args:
            branch: Branch name to query (default: "main")

        Returns:
            List of colocation center dictionaries with full field structure

        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubAPIError: If API error occurs
        """
        try:
            colocations = self._client.filters(
                kind="TopologyColocationCenter",
                branch=branch,
                prefetch_relationships=True
            )

            result = []
            for colo in colocations:
                colo_dict = {
                    "id": colo.id,
                    "name": {"value": getattr(colo.name, "value", None)},
                    "description": {"value": getattr(colo.description, "value", None) if hasattr(colo, "description") else None},
                }

                # Add relationships if they exist
                if hasattr(colo, "location") and colo.location.peer:
                    colo_dict["location"] = {
                        "node": {
                            "id": colo.location.peer.id,
                            "display_label": str(colo.location.peer)
                        }
                    }

                if hasattr(colo, "provider"):
                    colo_dict["provider"] = {"value": getattr(colo.provider, "value", None)}

                result.append(colo_dict)

            return result
        except Exception as e:
            raise InfrahubAPIError(f"Failed to fetch colocation centers: {str(e)}")

    def get_locations(self, branch: str = "main") -> List[Dict[str, Any]]:
        """Fetch LocationMetro objects.

        Args:
            branch: Branch name to query (default: "main")

        Returns:
            List of location dictionaries with id and name

        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubAPIError: If API error occurs
        """
        try:
            locations = self._client.filters(
                kind="LocationMetro",
                branch=branch,
                prefetch_relationships=False
            )

            result = []
            for loc in locations:
                loc_dict = {
                    "id": loc.id,
                    "name": {"value": getattr(loc.name, "value", None)},
                }

                result.append(loc_dict)

            return result
        except Exception as e:
            raise InfrahubAPIError(f"Failed to fetch locations: {str(e)}")

    def get_providers(self, branch: str = "main") -> List[Dict[str, Any]]:
        """Fetch OrganizationProvider objects.

        Args:
            branch: Branch name to query (default: "main")

        Returns:
            List of provider dictionaries with id and name

        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubAPIError: If API error occurs
        """
        try:
            providers = self._client.filters(
                kind="OrganizationProvider",
                branch=branch,
                prefetch_relationships=False
            )

            result = []
            for provider in providers:
                provider_dict = {
                    "id": provider.id,
                    "name": {"value": getattr(provider.name, "value", None)},
                }

                result.append(provider_dict)

            return result
        except Exception as e:
            raise InfrahubAPIError(f"Failed to fetch providers: {str(e)}")

    def get_designs(self, branch: str = "main") -> List[Dict[str, Any]]:
        """Fetch DesignTopology objects.

        Args:
            branch: Branch name to query (default: "main")

        Returns:
            List of design dictionaries with id and name

        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubAPIError: If API error occurs
        """
        try:
            designs = self._client.filters(
                kind="DesignTopology",
                branch=branch,
                prefetch_relationships=False
            )

            result = []
            for design in designs:
                design_dict = {
                    "id": design.id,
                    "name": {"value": getattr(design.name, "value", None)},
                }

                result.append(design_dict)

            return result
        except Exception as e:
            raise InfrahubAPIError(f"Failed to fetch designs: {str(e)}")

    def get_active_prefixes(self, branch: str = "main") -> List[Dict[str, Any]]:
        """Fetch active IpamPrefix objects.

        Args:
            branch: Branch name to query (default: "main")

        Returns:
            List of prefix dictionaries with id, prefix, and status

        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubAPIError: If API error occurs
        """
        try:
            # Use GraphQL to filter for active prefixes
            query = """
            query GetActivePrefixes {
                IpamPrefix(status__value: "active") {
                    edges {
                        node {
                            id
                            prefix { value }
                            status { value }
                        }
                    }
                }
            }
            """

            result = self.execute_graphql(query, branch=branch)

            prefixes = []
            edges = result.get("IpamPrefix", {}).get("edges", [])

            for edge in edges:
                node = edge.get("node", {})
                prefixes.append({
                    "id": node.get("id"),
                    "prefix": {"value": node.get("prefix", {}).get("value")},
                    "status": {"value": node.get("status", {}).get("value")},
                })

            return prefixes
        except Exception as e:
            raise InfrahubAPIError(f"Failed to fetch active prefixes: {str(e)}")

    def get_proposed_changes(self, branch: str = "main") -> List[Dict[str, Any]]:
        """Fetch proposed changes for a branch.

        Args:
            branch: Branch name to query (default: "main")

        Returns:
            List of proposed change dictionaries

        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubAPIError: If API error occurs
        """
        try:
            pcs = self._client.filters(kind="CoreProposedChange", branch=branch)

            result = []
            for pc in pcs:
                pc_dict = {
                    "id": pc.id,
                    "name": {"value": getattr(pc.name, "value", None)},
                    "state": {"value": getattr(pc.state, "value", None)},
                }

                if hasattr(pc, "source_branch"):
                    pc_dict["source_branch"] = {"value": getattr(pc.source_branch, "value", None)}

                result.append(pc_dict)

            return result
        except Exception as e:
            raise InfrahubAPIError(f"Failed to fetch proposed changes: {str(e)}")

    def execute_graphql(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        branch: str = "main",
    ) -> Dict[str, Any]:
        """Execute a GraphQL query or mutation.

        Args:
            query: GraphQL query or mutation string
            variables: Optional variables for the query
            branch: Branch name to execute against (default: "main")

        Returns:
            GraphQL response dictionary

        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubGraphQLError: If GraphQL error occurs
        """
        try:
            result = self._client.execute_graphql(
                query=query,
                variables=variables,
                branch_name=branch
            )
            return result
        except Exception as e:
            raise InfrahubGraphQLError(f"GraphQL error: {str(e)}", [])

    def create_branch(
        self, branch_name: str, from_branch: str = "main", sync_with_git: bool = False
    ) -> Dict[str, Any]:
        """Create a new branch in Infrahub.

        Args:
            branch_name: Name of the new branch
            from_branch: Branch to create from (default: "main")
            sync_with_git: Whether to sync with git (default: False)

        Returns:
            Dictionary with branch information

        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubAPIError: If API error occurs
        """
        try:
            branch = self._client.branch.create(
                branch_name=branch_name,
                sync_with_git=sync_with_git
            )
            return {
                "name": branch.name,
                "id": branch.id,
                "is_default": branch.is_default
            }
        except Exception as e:
            raise InfrahubAPIError(f"Failed to create branch: {str(e)}")

    def create_datacenter(
        self, branch: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a TopologyDataCenter object.

        Args:
            branch: Branch to create the object in
            data: Datacenter data dictionary with structure:
                - name: str
                - location: str (ID)
                - description: str
                - strategy: str
                - design: str
                - emulation: bool
                - provider: str
                - management_subnet: str (prefix ID)
                - customer_subnet: str (prefix ID)
                - technical_subnet: str (prefix ID)
                - member_of_groups: List[str]

        Returns:
            Created datacenter dictionary

        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubAPIError: If API error occurs
        """
        try:
            # Create datacenter with references to existing prefixes
            dc_mutation = """
            mutation CreateDataCenter(
                $name: String!,
                $location: String!,
                $description: String,
                $strategy: String!,
                $design: String!,
                $emulation: Boolean,
                $provider: String!,
                $mgmt_prefix_id: String!,
                $cust_prefix_id: String!,
                $tech_prefix_id: String!,
                $groups: [RelatedNodeInput]
            ) {
                TopologyDataCenterUpsert(
                    data: {
                        name: { value: $name }
                        location: { id: $location }
                        description: { value: $description }
                        strategy: { value: $strategy }
                        design: { id: $design }
                        emulation: { value: $emulation }
                        provider: { id: $provider }
                        management_subnet: { id: $mgmt_prefix_id }
                        customer_subnet: { id: $cust_prefix_id }
                        technical_subnet: { id: $tech_prefix_id }
                        member_of_groups: $groups
                    }
                ) {
                    ok
                    object {
                        id
                        name { value }
                    }
                }
            }
            """

            # Convert group strings to RelatedNodeInput format
            groups = [{"id": group} for group in data.get("member_of_groups", [])]

            dc_variables = {
                "name": data["name"],
                "location": data["location"],
                "description": data.get("description", ""),
                "strategy": data["strategy"],
                "design": data["design"],
                "emulation": data.get("emulation", False),
                "provider": data["provider"],
                "mgmt_prefix_id": data["management_subnet"],
                "cust_prefix_id": data["customer_subnet"],
                "tech_prefix_id": data["technical_subnet"],
                "groups": groups,
            }

            # Create the datacenter
            dc_result = self.execute_graphql(dc_mutation, dc_variables, branch)

            # Extract datacenter info from result
            if dc_result.get("TopologyDataCenterUpsert", {}).get("ok"):
                dc_obj = dc_result["TopologyDataCenterUpsert"]["object"]
                return {
                    "id": dc_obj["id"],
                    "name": dc_obj["name"]
                }
            else:
                raise InfrahubAPIError(f"Failed to create datacenter: {dc_result}")

        except Exception as e:
            raise InfrahubAPIError(f"Failed to create datacenter: {str(e)}")

    def create_proposed_change(
        self, branch: str, name: str, description: str, destination_branch: str = "main"
    ) -> Dict[str, Any]:
        """Create a proposed change for a branch.

        Args:
            branch: Branch name (source branch)
            name: Proposed change name
            description: Proposed change description
            destination_branch: Target branch for the proposed change (default: "main")

        Returns:
            Dictionary with proposed change information

        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubAPIError: If API error occurs
        """
        try:
            pc = self._client.create(
                kind="CoreProposedChange",
                branch=branch,
                name=name,
                description=description,
                source_branch=branch,
                destination_branch=destination_branch
            )
            pc.save(allow_upsert=True)

            return {
                "id": pc.id,
                "name": name
            }
        except Exception as e:
            raise InfrahubAPIError(f"Failed to create proposed change: {str(e)}")

    def get_proposed_change_url(self, pc_id: str) -> str:
        """Get the URL for a proposed change.

        Args:
            pc_id: Proposed change ID

        Returns:
            URL string for the proposed change
        """
        return f"{self.base_url}/proposed-changes/{pc_id}"

    def get_location_suites(self, branch: str = "main") -> List[Dict[str, Any]]:
        """Fetch LocationSuite objects.

        Args:
            branch: Branch name to query (default: "main")

        Returns:
            List of LocationSuite dictionaries with id and name

        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubAPIError: If API error occurs
        """
        try:
            suites = self._client.filters(
                kind="LocationSuite",
                branch=branch,
                prefetch_relationships=False
            )

            result = []
            for suite in suites:
                suite_dict = {
                    "id": suite.id,
                    "name": {"value": getattr(suite.name, "value", None)},
                }
                result.append(suite_dict)

            return result
        except Exception as e:
            raise InfrahubAPIError(f"Failed to fetch location suites: {str(e)}")

    def get_racks_by_suite(self, suite_id: str, branch: str = "main") -> List[Dict[str, Any]]:
        """Fetch LocationRack objects for a specific suite.

        Args:
            suite_id: LocationSuite ID
            branch: Branch name to query (default: "main")

        Returns:
            List of LocationRack dictionaries with id, name, height, and suite relationship

        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubAPIError: If API error occurs
        """
        try:
            # Use GraphQL to filter racks by parent (suite)
            query = """
            query GetRacksBySuite($suite_id: ID!) {
                LocationRack(parent__ids: [$suite_id]) {
                    edges {
                        node {
                            id
                            name { value }
                            shortname { value }
                            parent {
                                node {
                                    id
                                }
                            }
                        }
                    }
                }
            }
            """

            result = self.execute_graphql(query, {"suite_id": suite_id}, branch)

            racks = []
            edges = result.get("LocationRack", {}).get("edges", [])

            for edge in edges:
                node = edge.get("node", {})
                racks.append({
                    "id": node.get("id"),
                    "name": {"value": node.get("name", {}).get("value")},
                    "shortname": {"value": node.get("shortname", {}).get("value")},
                    # Default rack height to 42U (standard)
                    "height": {"value": 42},
                })

            return racks
        except Exception as e:
            raise InfrahubAPIError(f"Failed to fetch racks for suite: {str(e)}")

    def get_devices_by_rack(self, rack_id: str, branch: str = "main") -> List[Dict[str, Any]]:
        """Fetch DcimPhysicalDevice objects for a specific rack.

        Args:
            rack_id: LocationRack ID
            branch: Branch name to query (default: "main")

        Returns:
            List of DcimPhysicalDevice dictionaries with id, name, position, height, and device_type

        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubAPIError: If API error occurs
        """
        try:
            # Use GraphQL to filter devices by location (rack)
            query = """
            query GetDevicesByRack($rack_id: ID!) {
                DcimPhysicalDevice(location__ids: [$rack_id]) {
                    edges {
                        node {
                            id
                            name { value }
                            position { value }
                            device_type {
                                node {
                                    name { value }
                                    height { value }
                                }
                            }
                            location {
                                node {
                                    id
                                }
                            }
                        }
                    }
                }
            }
            """

            result = self.execute_graphql(query, {"rack_id": rack_id}, branch)

            devices = []
            edges = result.get("DcimPhysicalDevice", {}).get("edges", [])

            for edge in edges:
                node = edge.get("node", {})
                
                # Get height from device_type
                device_height = 1
                device_type_name = None
                device_type_node = node.get("device_type", {}).get("node")
                if device_type_node:
                    device_type_name = device_type_node.get("name", {}).get("value")
                    device_height = device_type_node.get("height", {}).get("value", 1)
                
                device_dict = {
                    "id": node.get("id"),
                    "name": {"value": node.get("name", {}).get("value")},
                    "position": {"value": node.get("position", {}).get("value")},
                    "height": {"value": device_height},
                }

                # Add device type if available
                if device_type_name:
                    device_dict["device_type"] = {"value": device_type_name}

                devices.append(device_dict)

            return devices
        except Exception as e:
            raise InfrahubAPIError(f"Failed to fetch devices for rack: {str(e)}")

    def _sdk_object_to_dict(self, obj: Any) -> Dict[str, Any]:
        """Convert an SDK object to a dictionary.

        Args:
            obj: SDK object

        Returns:
            Dictionary representation
        """
        return {
            "id": obj.id,
            "display_label": str(obj),
            "__typename": obj._schema.kind if hasattr(obj, "_schema") else None
        }
