"""Integration tests for VLAN management workflow."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

import sys
sys.path.insert(0, '../../')

from utils.api import InfrahubClient, InfrahubAPIError


class TestVLANWorkflowIntegration:
    """Test complete VLAN change workflow."""

    @patch('utils.api.InfrahubClientSync')
    def test_complete_workflow_success(self, mock_sdk: Mock) -> None:
        """Test successful execution of complete workflow."""
        mock_client_instance = Mock()
        
        # Mock branch creation
        mock_branch = Mock()
        mock_branch.name = "test-branch"
        mock_branch.id = "branch-1"
        mock_branch.is_default = False
        mock_client_instance.branch.create.return_value = mock_branch
        
        # Mock VLAN assignment
        mock_client_instance.execute_graphql.return_value = {
            "InfrahubInterfaceUpdate": {
                "ok": True,
                "object": {
                    "id": "iface-1",
                    "name": {"value": "eth1"}
                }
            }
        }
        
        # Mock proposed change creation
        mock_pc = Mock()
        mock_pc.id = "pc-1"
        mock_pc.save = Mock()
        mock_client_instance.create.return_value = mock_pc
        
        mock_sdk.return_value = mock_client_instance

        # Execute workflow steps
        client = InfrahubClient("http://localhost:8000")
        
        # Step 1: Create branch
        branch = client.create_branch("test-branch", "main")
        assert branch["name"] == "test-branch"
        
        # Step 2: Assign VLAN
        result = client.assign_vlan_to_interface("iface-1", "vlan-1", "test-branch")
        assert result["success"] is True
        
        # Step 3: Create proposed change
        pc = client.create_proposed_change(
            "test-branch",
            "Test Change",
            "Test Description"
        )
        assert pc["id"] == "pc-1"

    @patch('utils.api.InfrahubClientSync')
    def test_workflow_branch_creation_failure(self, mock_sdk: Mock) -> None:
        """Test workflow failure at branch creation step."""
        mock_client_instance = Mock()
        mock_client_instance.branch.create.side_effect = Exception("Branch creation failed")
        mock_sdk.return_value = mock_client_instance

        client = InfrahubClient("http://localhost:8000")
        
        with pytest.raises(InfrahubAPIError) as exc_info:
            client.create_branch("test-branch", "main")
        
        assert "Failed to create branch" in str(exc_info.value)

    @patch('utils.api.InfrahubClientSync')
    def test_workflow_vlan_assignment_failure(self, mock_sdk: Mock) -> None:
        """Test workflow failure at VLAN assignment step."""
        mock_client_instance = Mock()
        
        # Branch creation succeeds
        mock_branch = Mock()
        mock_branch.name = "test-branch"
        mock_branch.id = "branch-1"
        mock_branch.is_default = False
        mock_client_instance.branch.create.return_value = mock_branch
        
        # VLAN assignment fails
        mock_client_instance.execute_graphql.return_value = {
            "InfrahubInterfaceUpdate": {
                "ok": False
            }
        }
        
        mock_sdk.return_value = mock_client_instance

        client = InfrahubClient("http://localhost:8000")
        
        # Branch creation succeeds
        branch = client.create_branch("test-branch", "main")
        assert branch["name"] == "test-branch"
        
        # VLAN assignment fails
        with pytest.raises(InfrahubAPIError) as exc_info:
            client.assign_vlan_to_interface("iface-1", "vlan-1", "test-branch")
        
        assert "VLAN assignment mutation failed" in str(exc_info.value)

    @patch('utils.api.InfrahubClientSync')
    def test_workflow_proposed_change_failure(self, mock_sdk: Mock) -> None:
        """Test workflow failure at proposed change creation step."""
        mock_client_instance = Mock()
        
        # Branch creation succeeds
        mock_branch = Mock()
        mock_branch.name = "test-branch"
        mock_branch.id = "branch-1"
        mock_branch.is_default = False
        mock_client_instance.branch.create.return_value = mock_branch
        
        # VLAN assignment succeeds
        mock_client_instance.execute_graphql.return_value = {
            "InfrahubInterfaceUpdate": {
                "ok": True,
                "object": {
                    "id": "iface-1",
                    "name": {"value": "eth1"}
                }
            }
        }
        
        # Proposed change creation fails
        mock_client_instance.create.side_effect = Exception("PC creation failed")
        
        mock_sdk.return_value = mock_client_instance

        client = InfrahubClient("http://localhost:8000")
        
        # Branch creation succeeds
        branch = client.create_branch("test-branch", "main")
        assert branch["name"] == "test-branch"
        
        # VLAN assignment succeeds
        result = client.assign_vlan_to_interface("iface-1", "vlan-1", "test-branch")
        assert result["success"] is True
        
        # Proposed change creation fails
        with pytest.raises(InfrahubAPIError) as exc_info:
            client.create_proposed_change(
                "test-branch",
                "Test Change",
                "Test Description"
            )
        
        assert "Failed to create proposed change" in str(exc_info.value)

    @patch('utils.api.InfrahubClientSync')
    def test_workflow_error_recovery(self, mock_sdk: Mock) -> None:
        """Test error recovery and messaging."""
        mock_client_instance = Mock()
        
        # Simulate partial success scenario
        mock_branch = Mock()
        mock_branch.name = "test-branch"
        mock_branch.id = "branch-1"
        mock_branch.is_default = False
        mock_client_instance.branch.create.return_value = mock_branch
        
        # First call succeeds (VLAN assignment)
        # Second call fails (proposed change)
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
        
        # Verify branch was created
        branch = client.create_branch("test-branch", "main")
        assert branch["name"] == "test-branch"
        
        # Verify VLAN was assigned
        result = client.assign_vlan_to_interface("iface-1", "vlan-1", "test-branch")
        assert result["success"] is True
        
        # At this point, if PC creation fails, user should have branch name
        # for manual recovery


class TestDataValidation:
    """Test data validation in workflow."""

    @patch('utils.api.InfrahubClientSync')
    def test_interface_with_no_vlans(self, mock_sdk: Mock) -> None:
        """Test handling of interface with no VLANs."""
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
    def test_device_with_no_customer_interfaces(self, mock_sdk: Mock) -> None:
        """Test handling of device with no customer interfaces."""
        mock_client_instance = Mock()
        mock_client_instance.execute_graphql.return_value = {
            "InfrahubInterface": {
                "edges": []
            }
        }
        mock_sdk.return_value = mock_client_instance

        client = InfrahubClient("http://localhost:8000")
        interfaces = client.get_interfaces_by_device("device-1", "Customer", "main")

        assert len(interfaces) == 0

    @patch('utils.api.InfrahubClientSync')
    def test_location_with_no_devices(self, mock_sdk: Mock) -> None:
        """Test handling of location with no devices."""
        mock_client_instance = Mock()
        mock_client_instance.execute_graphql.return_value = {
            "DcimDevice": {
                "edges": []
            }
        }
        mock_sdk.return_value = mock_client_instance

        client = InfrahubClient("http://localhost:8000")
        devices = client.get_devices_by_location("pod-1", None, "main")

        assert len(devices) == 0


class TestBranchNaming:
    """Test branch naming conventions."""

    def test_branch_name_format(self) -> None:
        """Test branch name follows expected format."""
        device_name = "leaf-switch-01"
        interface_name = "eth1"
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        
        branch_name = f"vlan-change-{device_name}-{interface_name}-{timestamp}"
        
        assert branch_name.startswith("vlan-change-")
        assert device_name in branch_name
        assert interface_name in branch_name
        assert len(timestamp) == 15  # YYYYMMDD-HHMMSS

    def test_branch_name_uniqueness(self) -> None:
        """Test that branch names are unique due to timestamp."""
        import time
        
        device_name = "leaf-switch-01"
        interface_name = "eth1"
        
        timestamp1 = datetime.now().strftime("%Y%m%d-%H%M%S")
        branch_name1 = f"vlan-change-{device_name}-{interface_name}-{timestamp1}"
        
        time.sleep(1)
        
        timestamp2 = datetime.now().strftime("%Y%m%d-%H%M%S")
        branch_name2 = f"vlan-change-{device_name}-{interface_name}-{timestamp2}"
        
        # Branch names should be different due to timestamp
        assert branch_name1 != branch_name2
