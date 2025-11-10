"""Infrahub API client for the Service Catalog."""

import time
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


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
    """Client for interacting with the Infrahub API."""
    
    def __init__(self, base_url: str, timeout: int = 30, ui_url: Optional[str] = None):
        """Initialize the Infrahub API client.
        
        Args:
            base_url: Base URL of the Infrahub instance for API calls (e.g., "http://infrahub-server:8000")
            timeout: Request timeout in seconds (default: 30)
            ui_url: Optional UI URL for generating user-facing links (defaults to base_url)
        """
        self.base_url = base_url.rstrip("/")
        self.ui_url = (ui_url or base_url).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        
        # Configure retry strategy for transient errors
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,  # Will result in delays of 1s, 2s, 4s
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def _make_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, str]] = None,
    ) -> requests.Response:
        """Make an HTTP request with error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            headers: Optional request headers
            json_data: Optional JSON data for POST requests
            params: Optional query parameters
            
        Returns:
            Response object
            
        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubHTTPError: If HTTP error occurs
        """
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response
        except requests.exceptions.ConnectionError as e:
            raise InfrahubConnectionError(
                f"Unable to connect to Infrahub at {self.base_url}. "
                f"Please check that Infrahub is running."
            ) from e
        except requests.exceptions.Timeout as e:
            raise InfrahubConnectionError(
                f"Request to Infrahub timed out after {self.timeout} seconds."
            ) from e
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else 0
            response_text = e.response.text if e.response else ""
            raise InfrahubHTTPError(
                f"HTTP {status_code} error from Infrahub: {str(e)}",
                status_code=status_code,
                response_text=response_text
            ) from e
    
    def get_branches(self) -> List[Dict[str, Any]]:
        """Fetch all branches from Infrahub via GraphQL API.
        
        Returns:
            List of branch dictionaries with id, name, description, etc.
            
        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubHTTPError: If HTTP error occurs
            InfrahubGraphQLError: If GraphQL error occurs
        """
        query = """
        query GetBranches {
          Branch {
            id
            name
            description
            is_default
            sync_with_git
          }
        }
        """
        
        result = self.execute_graphql(query)
        
        # Extract branches from GraphQL response
        branches = result.get("data", {}).get("Branch", [])
        
        return branches
    
    def get_objects(
        self,
        object_type: str,
        branch: str = "main"
    ) -> List[Dict[str, Any]]:
        """Fetch objects of a given type from Infrahub via GraphQL API.
        
        This is a generic method. For specific object types like TopologyDataCenter,
        use the dedicated methods (get_datacenters, get_colocation_centers) which
        fetch all required fields.
        
        Args:
            object_type: Type of object to fetch (e.g., "TopologyDataCenter")
            branch: Branch name to query (default: "main")
            
        Returns:
            List of object dictionaries
            
        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubHTTPError: If HTTP error occurs
            InfrahubGraphQLError: If GraphQL error occurs
        """
        # Use specific methods for known types
        if object_type == "TopologyDataCenter":
            return self.get_datacenters(branch)
        elif object_type == "TopologyColocationCenter":
            return self.get_colocation_centers(branch)
        
        # Generic query for other types
        query = f"""
        query GetObjects {{
          {object_type} {{
            edges {{
              node {{
                id
                display_label
                __typename
              }}
            }}
          }}
        }}
        """
        
        result = self.execute_graphql(query, branch=branch)
        
        # Extract objects from GraphQL response
        edges = result.get("data", {}).get(object_type, {}).get("edges", [])
        objects = [edge["node"] for edge in edges]
        
        return objects
    
    def get_datacenters(self, branch: str = "main") -> List[Dict[str, Any]]:
        """Fetch TopologyDataCenter objects with all required fields.
        
        Args:
            branch: Branch name to query (default: "main")
            
        Returns:
            List of datacenter dictionaries with full field structure
            
        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubHTTPError: If HTTP error occurs
            InfrahubGraphQLError: If GraphQL error occurs
        """
        query = """
        query GetDataCenters {
          TopologyDataCenter {
            edges {
              node {
                id
                name {
                  value
                }
                description {
                  value
                }
                strategy {
                  value
                }
                location {
                  node {
                    id
                    display_label
                  }
                }
                design {
                  node {
                    id
                    name {
                      value
                    }
                  }
                }
              }
            }
          }
        }
        """
        
        result = self.execute_graphql(query, branch=branch)
        
        # Extract datacenters from GraphQL response
        edges = result.get("data", {}).get("TopologyDataCenter", {}).get("edges", [])
        datacenters = [edge["node"] for edge in edges]
        
        return datacenters
    
    def get_colocation_centers(self, branch: str = "main") -> List[Dict[str, Any]]:
        """Fetch TopologyColocationCenter objects with all required fields.
        
        Args:
            branch: Branch name to query (default: "main")
            
        Returns:
            List of colocation center dictionaries with full field structure
            
        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubHTTPError: If HTTP error occurs
            InfrahubGraphQLError: If GraphQL error occurs
        """
        query = """
        query GetColocationCenters {
          TopologyColocationCenter {
            edges {
              node {
                id
                name {
                  value
                }
                description {
                  value
                }
                location {
                  node {
                    id
                    display_label
                  }
                }
                provider {
                  value
                }
              }
            }
          }
        }
        """
        
        result = self.execute_graphql(query, branch=branch)
        
        # Extract colocation centers from GraphQL response
        edges = result.get("data", {}).get("TopologyColocationCenter", {}).get("edges", [])
        colocations = [edge["node"] for edge in edges]
        
        return colocations
    
    def execute_graphql(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        branch: str = "main"
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
            InfrahubHTTPError: If HTTP error occurs
            InfrahubGraphQLError: If GraphQL error occurs
        """
        url = f"{self.base_url}/graphql"
        headers = {
            "Content-Type": "application/json",
            "X-INFRAHUB-BRANCH": branch
        }
        
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        response = self._make_request("POST", url, headers=headers, json_data=payload)
        result = response.json()
        
        # Check for GraphQL errors
        if "errors" in result:
            error_messages = [err.get("message", str(err)) for err in result["errors"]]
            raise InfrahubGraphQLError(
                f"GraphQL errors: {'; '.join(error_messages)}",
                errors=result["errors"]
            )
        
        return result

    def create_branch(
        self,
        branch_name: str,
        from_branch: str = "main",
        sync_with_git: bool = False
    ) -> Dict[str, Any]:
        """Create a new branch in Infrahub.
        
        Args:
            branch_name: Name of the new branch
            from_branch: Branch to create from (default: "main")
            sync_with_git: Whether to sync with git (default: False)
            
        Returns:
            Dictionary with branch creation result
            
        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubHTTPError: If HTTP error occurs
            InfrahubGraphQLError: If GraphQL error occurs
        """
        mutation = """
        mutation CreateBranch($name: String!, $sync_with_git: Boolean) {
          BranchCreate(data: {name: $name, sync_with_git: $sync_with_git}) {
            ok
            object {
              id
              name
            }
          }
        }
        """
        
        variables = {
            "name": branch_name,
            "sync_with_git": sync_with_git
        }
        
        result = self.execute_graphql(mutation, variables=variables, branch=from_branch)
        
        # Check if mutation was successful
        branch_create = result.get("data", {}).get("BranchCreate", {})
        if not branch_create.get("ok"):
            raise InfrahubAPIError(f"Failed to create branch '{branch_name}'")
        
        return branch_create.get("object", {})
    
    def create_datacenter(
        self,
        branch: str,
        dc_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new DataCenter in Infrahub.
        
        Args:
            branch: Branch to create the datacenter in
            dc_data: Dictionary containing datacenter attributes:
                - name: str
                - location: str
                - description: str (optional)
                - strategy: str
                - design: str (design ID)
                - emulation: bool (optional)
                - provider: str
                - management_subnet: dict with prefix, status, role
                - customer_subnet: dict with prefix, status, role
                - technical_subnet: dict with prefix, status, role
                - member_of_groups: list of group IDs (optional)
            
        Returns:
            Dictionary with datacenter creation result
            
        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubHTTPError: If HTTP error occurs
            InfrahubGraphQLError: If GraphQL error occurs
        """
        mutation = """
        mutation CreateDataCenter(
          $name: String!,
          $location: String!,
          $description: String,
          $strategy: String!,
          $design: String!,
          $emulation: Boolean,
          $provider: String!,
          $management_subnet: RelatedIPPrefixInput!,
          $customer_subnet: RelatedIPPrefixInput!,
          $technical_subnet: RelatedIPPrefixInput!,
          $member_of_groups: [String]
        ) {
          TopologyDataCenterCreate(data: {
            name: {value: $name},
            location: {value: $location},
            description: {value: $description},
            strategy: {value: $strategy},
            design: {id: $design},
            emulation: {value: $emulation},
            provider: {value: $provider},
            management_subnet: $management_subnet,
            customer_subnet: $customer_subnet,
            technical_subnet: $technical_subnet,
            member_of_groups: $member_of_groups
          }) {
            ok
            object {
              id
              name {
                value
              }
            }
          }
        }
        """
        
        # Prepare variables from dc_data
        variables = {
            "name": dc_data["name"],
            "location": dc_data["location"],
            "description": dc_data.get("description", ""),
            "strategy": dc_data["strategy"],
            "design": dc_data["design"],
            "emulation": dc_data.get("emulation", False),
            "provider": dc_data["provider"],
            "management_subnet": dc_data["management_subnet"],
            "customer_subnet": dc_data["customer_subnet"],
            "technical_subnet": dc_data["technical_subnet"],
        }
        
        # Add optional member_of_groups if provided
        if "member_of_groups" in dc_data:
            variables["member_of_groups"] = dc_data["member_of_groups"]
        
        result = self.execute_graphql(mutation, variables=variables, branch=branch)
        
        # Check if mutation was successful
        dc_create = result.get("data", {}).get("TopologyDataCenterCreate", {})
        if not dc_create.get("ok"):
            raise InfrahubAPIError(f"Failed to create datacenter '{dc_data['name']}'")
        
        return dc_create.get("object", {})
    
    def create_proposed_change(
        self,
        branch: str,
        name: str,
        description: str = ""
    ) -> Dict[str, Any]:
        """Create a Proposed Change for a branch.
        
        Args:
            branch: Source branch for the proposed change
            name: Name of the proposed change
            description: Description of the proposed change (optional)
            
        Returns:
            Dictionary with proposed change creation result
            
        Raises:
            InfrahubConnectionError: If connection fails
            InfrahubHTTPError: If HTTP error occurs
            InfrahubGraphQLError: If GraphQL error occurs
        """
        mutation = """
        mutation CreateProposedChange(
          $name: String!,
          $description: String,
          $source_branch: String!
        ) {
          CoreProposedChangeCreate(data: {
            name: {value: $name},
            description: {value: $description},
            source_branch: {value: $source_branch}
          }) {
            ok
            object {
              id
              name {
                value
              }
            }
          }
        }
        """
        
        variables = {
            "name": name,
            "description": description,
            "source_branch": branch
        }
        
        result = self.execute_graphql(mutation, variables=variables, branch=branch)
        
        # Check if mutation was successful
        pc_create = result.get("data", {}).get("CoreProposedChangeCreate", {})
        if not pc_create.get("ok"):
            raise InfrahubAPIError(f"Failed to create proposed change '{name}'")
        
        return pc_create.get("object", {})
    
    def get_proposed_change_url(self, pc_id: str) -> str:
        """Generate URL to a Proposed Change in the Infrahub UI.
        
        Args:
            pc_id: ID of the proposed change
            
        Returns:
            Full URL to the proposed change in the UI
        """
        return f"{self.ui_url}/proposed-changes/{pc_id}"
