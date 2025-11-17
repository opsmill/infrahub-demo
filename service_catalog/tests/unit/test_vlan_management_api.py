"""Unit tests for VLAN management API client methods."""

import pytest
from unittest.mock import Mock, patch

# Mock the imports to avoid dependency issues in tests
import sys
sys.path.insert(0, '../../')

from utils.api import InfrahubClient, InfrahubAPIError


class TestLocationMethods:
    """Test location-related API methods."""

    @patch('utils.api.InfrahubClientSync')
    def test_get_location_buildings_success(self, mock_sdk: Mock) -> None:
        """Test successful retrieval of location buildings."""
        # Setup mock
        mock_building = Mock()
        mock_building.id = "building-1"
        mock_building.name = Mock()
        mock_building.name.value = "Building A"

        mock_client_instance = Mock()
        mock_client_instance.filters.return_value = [mock_building]
        mock_sdk.return_value = mock_client_instance

        # Test
        client = InfrahubClient("http://localhost:8000")
        buildings = client.get_location_buildings("main")

        # Assertions
        assert len(buildings) == 1
        assert buildings[0]["id"] == "building-1"
        assert buildings[0]["name"]["value"] == "Building A"
        mock_client_instance.filters.assert_called_once_with(
            kind="LocationBuilding",
            branch="main",
            prefetch_relationships=False
        )

    @patch('utils.api.InfrahubClientSync')
    def test_get_location_buildings_empty(self, mock_sdk: Mock) -> None:
        """Test retrieval when no buildings exist."""
        mock_client_instance = Mock()
        mock_client_instance.filters.return_value = []
        mock_sdk.return_value = mock_client_instance

        client = InfrahubClient("http://localhost:8000")
        buildings = client.get_location_buildings("main")

        assert len(buildings) == 0

    @patch('utils.api.InfrahubClientSync')
    def test_get_pods_by_building_success(self, mock_sdk: Mock) -> None:
        """Test successful retrieval of pods by building."""
        mock_client_instance = Mock()
        mock_client_instance.execute_graphql.return_value = {
            "LocationPod": {
                "edges": [
                    {
                        "node": {
                            "id": "pod-1",
                            "name": {"value": "Pod 1"}
                        }
                    }
                ]
            }
        }
        mock_sdk.return_value = mock_client_instance

        client = InfrahubClient("http://localhost:8000")
        pods = client.get_pods_by_building("building-1", "main")

        assert len(pods) == 1
        assert pods[0]["id"] == "pod-1"
        assert pods[0]["name"]["value"] == "Pod 1"

    @patch('utils.api.InfrahubClientSync')
    def test_get_racks_by_pod_success(self, mock_sdk: Mock) -> None:
        """Test successful retrieval of racks by pod."""
        mock_client_instance = Mock()
        mock_client_instance.execute_graphql.return_value = {
            "LocationRack": {
                "edges": [
                    {
                        "node": {
                            "id": "rack-1",
                            "name": {"value": "Rack A1"}
                        }
                    }
                ]
            }
        }
        mock_sdk.return_value = mock_client_instance

        client = InfrahubClient("http://localhost:8000")
        racks = client.get_racks_by_pod("pod-1", "main")

        assert len(racks) == 1
        assert racks[0]["id"] == "rack-1"
        assert racks[0]["name"]["value"] == "Rack A1"

    @patch('utils.api.InfrahubClientSync')
    def test_get_devices_by_location_with_rack(self, mock_sdk: Mock) -> None:
        """Test retrieval of devices filtered by specific rack."""
        mock_client_instance = Mock()
        mock_client_instance.execute_graphql.return_value = {
            "DcimDevice": {
                "edges": [
                    {
                        "node": {
                            "id": "device-1",
                            "name": {"value": "leaf-switch-01"}
                        }
                    }
                ]
            }
        }
        mock_sdk.return_value = mock_client_instance

        client = InfrahubClient("http://localhost:8000")
        devices = client.get_devices_by_location("pod-1", "rack-1", "main")

        assert len(devices) == 1
        assert devices[0]["id"] == "device-1"
        assert devices[0]["name"]["value"] == "leaf-switch-01"

    @patch('utils.api.InfrahubClientSync')
    def test_get_devices_by_location_all_racks(self, mock_sdk: Mock) -> None:
        """Test retrieval of devices from all racks in pod."""
        mock_client_instance = Mock()
        mock_client_instance.execute_graphql.return_value = {
            "DcimDevice": {
                "edges": [
                    {
                        "node": {
                            "id": "device-1",
                            "name": {"value": "leaf-switch-01"}
                        }
                    },
                    {
                        "node": {
                            "id": "device-2",
                            "name": {"value": "leaf-switch-02"}
                        }
                    }
                ]
            }
        }
        mock_sdk.return_value = mock_client_instance

        client = InfrahubClient("http://localhost:8000")
        devices = client.get_devices_by_location("pod-1", None, "main")

        assert len(devices) == 2


class TestInterfaceMethods:
    """Test interface-related API methods."""

    @patch('utils.api.InfrahubClientSync')
    def test_get_interfaces_by_device_with_role_filter(self, mock_sdk: Mock) -> None:
        """Test retrieval of interfaces filtered by role."""
        mock_client_instance = Mock()
        mock_client_instance.execute_graphql.return_value = {
            "InfrahubInterface": {
                "edges": [
                    {
                        "node": {
                            "id": "iface-1",
                            "name": {"value": "eth1"},
                            "description": {"value": "Customer Port"},
                            "role": {"value": "Customer"}
                        }
                    }
                ]
            }
        }
        mock_sdk.return_value = mock_client_instance

        client = InfrahubClient("http://localhost:8000")
        interfaces = client.get_interfaces_by_device("device-1", "Customer", "main")

        assert len(interfaces) == 1
        assert interfaces[0]["id"] == "iface-1"
        assert interfaces[0]["role"]["value"] == "Customer"

    @patch('utils.api.InfrahubClientSync')
    def test_get_interfaces_by_device_no_filter(self, mock_sdk: Mock) -> None:
        """Test retrieval of all interfaces without role filter."""
        mock_client_instance = Mock()
        mock_client_instance.execute_graphql.return_value = {
            "InfrahubInterface": {
                "edges": [
                    {
                        "node": {
                            "id": "iface-1",
                            "name": {"value": "eth1"},
                            "description": {"value": "Port 1"},
                            "role": {"value": "Uplink"}
                        }
                    },
                    {
                        "node": {
                            "id": "iface-2",
                            "name": {"value": "eth2"},
                            "description": {"value": "Port 2"},
                            "role": {"value": "Customer"}
                        }
                    }
                ]
            }
        }
        mock_sdk.return_value = mock_client_instance

        client = InfrahubClient("http://localhost:8000")
        interfaces = client.get_interfaces_by_device("device-1", None, "main")

        assert len(interfaces) == 2


class TestVLANMethods:
    """Test VLAN-related API methods."""

    @patch('utils.api.InfrahubClientSync')
    def test_get_vlans_by_interface_success(self, mock_sdk: Mock) -> None:
        """Test retrieval of VLANs assigned to interface."""
        mock_client_instance = Mock()
        mock_client_instance.execute_graphql.return_value = {
            "InfrahubInterface": {
                "edges": [
                    {
                        "node": {
                            "id": "iface-1",
                            "vlans": {
                                "edges": [
                                    {
                                        "node": {
                                            "id": "vlan-1",
                                            "vlan_id": {"value": 100},
                                            "name": {"value": "Production"},
                                            "description": {"value": "Prod VLAN"}
                                        }
                                    }
                                ]
                            }
                        }
                    }
                ]
            }
        }
        mock_sdk.return_value = mock_client_instance

        client = InfrahubClient("http://localhost:8000")
        vlans = client.get_vlans_by_interface("iface-1", "main")

        assert len(vlans) == 1
        assert vlans[0]["vlan_id"]["value"] == 100
        assert vlans[0]["name"]["value"] == "Production"

    @patch('utils.api.InfrahubClientSync')
    def test_get_vlans_by_interface_empty(self, mock_sdk: Mock) -> None:
        """Test retrieval when no VLANs assigned."""
        mock_client_instance = Mock()
        mock_client_instance.execute_graphql.return_value = {
            "InfrahubInterface": {
                "edges": [
                    {
                        "node": {
                            "id": "iface-1",
                            "vlans": {
                                "edges": []
                            }
                        }
                    }
                ]
            }
        }
        mock_sdk.return_value = mock_client_instance

        client = InfrahubClient("http://localhost:8000")
        vlans = client.get_vlans_by_interface("iface-1", "main")

        assert len(vlans) == 0

    @patch('utils.api.InfrahubClientSync')
    def test_get_all_vlans_success(self, mock_sdk: Mock) -> None:
        """Test retrieval of all VLANs."""
        mock_vlan = Mock()
        mock_vlan.id = "vlan-1"
        mock_vlan.vlan_id = Mock()
        mock_vlan.vlan_id.value = 100
        mock_vlan.name = Mock()
        mock_vlan.name.value = "Production"
        mock_vlan.description = Mock()
        mock_vlan.description.value = "Prod VLAN"

        mock_client_instance = Mock()
        mock_client_instance.filters.return_value = [mock_vlan]
        mock_sdk.return_value = mock_client_instance

        client = InfrahubClient("http://localhost:8000")
        vlans = client.get_all_vlans("main")

        assert len(vlans) == 1
        assert vlans[0]["vlan_id"]["value"] == 100

    @patch('utils.api.InfrahubClientSync')
    def test_assign_vlan_to_interface_success(self, mock_sdk: Mock) -> None:
        """Test successful VLAN assignment."""
        mock_client_instance = Mock()
        mock_client_instance.execute_graphql.return_value = {
            "InfrahubInterfaceUpdate": {
                "ok": True,
                "object": {
                    "id": "iface-1",
                    "name": {"value": "eth1"}
                }
            }
        }
        mock_sdk.return_value = mock_client_instance

        client = InfrahubClient("http://localhost:8000")
        result = client.assign_vlan_to_interface("iface-1", "vlan-1", "test-branch")

        assert result["success"] is True
        assert result["interface"]["id"] == "iface-1"

    @patch('utils.api.InfrahubClientSync')
    def test_assign_vlan_to_interface_failure(self, mock_sdk: Mock) -> None:
        """Test VLAN assignment failure."""
        mock_client_instance = Mock()
        mock_client_instance.execute_graphql.return_value = {
            "InfrahubInterfaceUpdate": {
                "ok": False
            }
        }
        mock_sdk.return_value = mock_client_instance

        client = InfrahubClient("http://localhost:8000")
        
        with pytest.raises(InfrahubAPIError):
            client.assign_vlan_to_interface("iface-1", "vlan-1", "test-branch")


class TestErrorHandling:
    """Test error handling in API methods."""

    @patch('utils.api.InfrahubClientSync')
    def test_get_location_buildings_error(self, mock_sdk: Mock) -> None:
        """Test error handling when fetching buildings fails."""
        mock_client_instance = Mock()
        mock_client_instance.filters.side_effect = Exception("Connection failed")
        mock_sdk.return_value = mock_client_instance

        client = InfrahubClient("http://localhost:8000")
        
        with pytest.raises(InfrahubAPIError) as exc_info:
            client.get_location_buildings("main")
        
        assert "Failed to fetch location buildings" in str(exc_info.value)

    @patch('utils.api.InfrahubClientSync')
    def test_get_pods_by_building_error(self, mock_sdk: Mock) -> None:
        """Test error handling when fetching pods fails."""
        mock_client_instance = Mock()
        mock_client_instance.execute_graphql.side_effect = Exception("GraphQL error")
        mock_sdk.return_value = mock_client_instance

        client = InfrahubClient("http://localhost:8000")
        
        with pytest.raises(InfrahubAPIError) as exc_info:
            client.get_pods_by_building("building-1", "main")
        
        assert "Failed to fetch pods for building" in str(exc_info.value)
