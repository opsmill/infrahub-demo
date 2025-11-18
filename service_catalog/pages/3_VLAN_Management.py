"""Infrahub Service Catalog - VLAN Management Page.

This page provides a form-based interface for modifying VLAN assignments
on customer-facing ports of leaf switches.
"""

import streamlit as st
from datetime import datetime
from typing import Any, Dict, Optional

from utils import (
    INFRAHUB_ADDRESS,
    INFRAHUB_API_TOKEN,
    INFRAHUB_UI_URL,
    InfrahubClient,
    display_error,
    display_logo,
    display_progress,
    display_success,
)
from utils.api import (
    InfrahubAPIError,
    InfrahubConnectionError,
    InfrahubGraphQLError,
    InfrahubHTTPError,
)


# Configure page layout and title
st.set_page_config(
    page_title="VLAN Management - Infrahub Service Catalog",
    page_icon="🏷️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session state
if "infrahub_url" not in st.session_state:
    st.session_state.infrahub_url = INFRAHUB_ADDRESS


def render_location_selectors(client: InfrahubClient) -> Dict[str, Optional[str]]:
    """Render hierarchical location selector dropdowns.

    Args:
        client: InfrahubClient instance

    Returns:
        Dictionary with selected IDs:
        {
            "building_id": str or None,
            "pod_id": str or None,
            "rack_id": str or None,
            "device_id": str or None
        }
    """
    selections: Dict[str, Optional[str]] = {
        "building_id": None,
        "pod_id": None,
        "rack_id": None,
        "device_id": None
    }

    st.markdown("### 📍 Location Selection")

    # Building selector
    cache_key = "location_buildings_main"
    if cache_key not in st.session_state:
        with st.spinner("Loading buildings..."):
            try:
                st.session_state[cache_key] = client.get_location_buildings("main")
            except (InfrahubConnectionError, InfrahubHTTPError, InfrahubGraphQLError) as e:
                display_error("Failed to load buildings", str(e))
                return selections
            except Exception as e:
                display_error("Unexpected error loading buildings", str(e))
                return selections

    buildings = st.session_state[cache_key]

    if not buildings:
        st.warning("No buildings found. Please create LocationBuilding objects in Infrahub.")
        return selections

    building_names = [b.get("name", {}).get("value", "Unknown") for b in buildings]
    building_map = {b.get("name", {}).get("value", "Unknown"): b.get("id") for b in buildings}

    selected_building_name = st.selectbox(
        "Building",
        options=building_names,
        help="Select the building where the device is located",
        key="building_selector",
    )

    if selected_building_name:
        selections["building_id"] = building_map.get(selected_building_name)

        # Pod selector
        building_id = selections["building_id"]
        if not building_id:
            return selections

        with st.spinner("Loading pods..."):
            try:
                pods = client.get_pods_by_building(building_id, "main")
            except (InfrahubAPIError, InfrahubConnectionError) as e:
                display_error("Failed to load pods", str(e))
                return selections

        if not pods:
            st.info(f"No pods found in building '{selected_building_name}'.")
            return selections

        pod_names = [p.get("name", {}).get("value", "Unknown") for p in pods]
        pod_map = {p.get("name", {}).get("value", "Unknown"): p.get("id") for p in pods}

        selected_pod_name = st.selectbox(
            "Pod",
            options=pod_names,
            help="Select the pod within the building",
            key="pod_selector",
        )

        if selected_pod_name:
            selections["pod_id"] = pod_map.get(selected_pod_name)

            # Rack selector (optional)
            pod_id = selections["pod_id"]
            if not pod_id:
                return selections

            with st.spinner("Loading racks..."):
                try:
                    racks = client.get_racks_by_pod(pod_id, "main")
                except (InfrahubAPIError, InfrahubConnectionError) as e:
                    display_error("Failed to load racks", str(e))
                    return selections

            rack_options = ["All Racks"] + [r.get("name", {}).get("value", "Unknown") for r in racks]
            rack_map = {r.get("name", {}).get("value", "Unknown"): r.get("id") for r in racks}

            selected_rack_option = st.selectbox(
                "Rack (Optional)",
                options=rack_options,
                help="Select a specific rack or view all racks in the pod",
                key="rack_selector",
            )

            if selected_rack_option and selected_rack_option != "All Racks":
                selections["rack_id"] = rack_map.get(selected_rack_option)

            # Device selector
            with st.spinner("Loading devices..."):
                try:
                    devices = client.get_devices_by_location(
                        pod_id,
                        selections["rack_id"],
                        "main"
                    )
                except (InfrahubAPIError, InfrahubConnectionError) as e:
                    display_error("Failed to load devices", str(e))
                    return selections

            if not devices:
                st.info("No devices found in the selected location.")
                return selections

            device_names = [d.get("name", {}).get("value", "Unknown") for d in devices]
            device_map = {d.get("name", {}).get("value", "Unknown"): d.get("id") for d in devices}

            selected_device_name = st.selectbox(
                "Device",
                options=device_names,
                help="Select the device to manage VLANs on",
                key="device_selector",
            )

            if selected_device_name:
                selections["device_id"] = device_map.get(selected_device_name)

    return selections


def render_interface_selector(
    client: InfrahubClient,
    device_id: str,
    device_name: str
) -> Optional[Dict[str, Any]]:
    """Render interface dropdown filtered to customer interfaces.

    Args:
        client: InfrahubClient instance
        device_id: Selected device ID
        device_name: Selected device name for display

    Returns:
        Dictionary with interface info or None:
        {
            "id": str,
            "name": str,
            "description": str
        }
    """
    st.markdown("### 🔌 Interface Selection")

    with st.spinner("Loading interfaces..."):
        try:
            interfaces = client.get_interfaces_by_device(
                device_id,
                role_filter="Customer",
                branch="main"
            )
        except (InfrahubAPIError, InfrahubConnectionError) as e:
            display_error("Failed to load interfaces", str(e))
            return None

    if not interfaces:
        st.info(f"No customer interfaces found on device '{device_name}'.")
        return None

    # Format interface options as "name - description"
    interface_options = []
    interface_map = {}
    for iface in interfaces:
        name = iface.get("name", {}).get("value", "Unknown")
        desc = iface.get("description", {}).get("value", "")
        display_text = f"{name} - {desc}" if desc else name
        interface_options.append(display_text)
        interface_map[display_text] = {
            "id": iface.get("id"),
            "name": name,
            "description": desc
        }

    selected_interface_display = st.selectbox(
        "Customer Interface",
        options=interface_options,
        help="Select a customer-facing interface to manage VLANs",
        key="interface_selector",
    )

    if selected_interface_display:
        return interface_map.get(selected_interface_display)

    return None


def render_current_vlans(
    client: InfrahubClient,
    interface_id: str
) -> None:
    """Display current VLAN assignments for the interface.

    Args:
        client: InfrahubClient instance
        interface_id: Selected interface ID
    """
    st.markdown("**Current VLAN Assignments:**")

    with st.spinner("Loading current VLANs..."):
        try:
            current_vlans = client.get_vlans_by_interface(interface_id, "main")
        except (InfrahubAPIError, InfrahubConnectionError) as e:
            display_error("Failed to load current VLANs", str(e))
            return

    if not current_vlans:
        st.caption("No VLANs currently assigned to this interface.")
    else:
        for vlan in current_vlans:
            vlan_id = vlan.get("vlan_id", {}).get("value", "N/A")
            vlan_name = vlan.get("name", {}).get("value", "Unknown")
            st.markdown(f"• VLAN {vlan_id} - {vlan_name}")


def render_vlan_selector(client: InfrahubClient) -> Optional[Dict[str, Any]]:
    """Render VLAN dropdown with all available VLANs.

    Args:
        client: InfrahubClient instance

    Returns:
        Dictionary with VLAN info or None:
        {
            "id": str,
            "vlan_id": int,
            "name": str
        }
    """
    st.markdown("### 🏷️ New VLAN Assignment")

    # Cache VLANs
    cache_key = "all_vlans_main"
    if cache_key not in st.session_state:
        with st.spinner("Loading VLANs..."):
            try:
                st.session_state[cache_key] = client.get_all_vlans("main")
            except (InfrahubConnectionError, InfrahubHTTPError, InfrahubGraphQLError) as e:
                display_error("Failed to load VLANs", str(e))
                return None
            except Exception as e:
                display_error("Unexpected error loading VLANs", str(e))
                return None

    vlans = st.session_state[cache_key]

    if not vlans:
        st.warning("No VLANs found. Please create InterfaceVirtual objects in Infrahub.")
        return None

    # Format VLAN options as "VLAN ID - Name"
    vlan_options = []
    vlan_map = {}
    for vlan in vlans:
        vlan_id = vlan.get("vlan_id", {}).get("value")
        vlan_name = vlan.get("name", {}).get("value", "Unknown")
        if vlan_id is not None:
            display_text = f"VLAN {vlan_id} - {vlan_name}"
            vlan_options.append(display_text)
            vlan_map[display_text] = {
                "id": vlan.get("id"),
                "vlan_id": vlan_id,
                "name": vlan_name
            }

    if not vlan_options:
        st.warning("No valid VLANs found.")
        return None

    selected_vlan_display = st.selectbox(
        "Select VLAN",
        options=vlan_options,
        help="Choose a VLAN to assign to the interface",
        key="vlan_selector",
    )

    if selected_vlan_display:
        return vlan_map.get(selected_vlan_display)

    return None


def execute_vlan_change_workflow(
    client: InfrahubClient,
    device_name: str,
    interface_name: str,
    interface_id: str,
    vlan_id: str,
    vlan_name: str
) -> None:
    """Execute the complete VLAN change workflow.

    Args:
        client: InfrahubClient instance
        device_name: Name of the device
        interface_name: Name of the interface
        interface_id: Interface ID
        vlan_id: VLAN ID to assign
        vlan_name: VLAN name for display

    Workflow:
        1. Create new branch
        2. Apply VLAN assignment
        3. Create proposed change
        4. Display result with URL
    """
    # Generate unique branch name
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    branch_name = f"vlan-change-{device_name}-{interface_name}-{timestamp}"

    try:
        # Step 1: Create branch
        with st.spinner("Creating branch..."):
            display_progress("Creating branch", 0.33)
            client.create_branch(branch_name, from_branch="main")
            st.success(f"✅ Branch created: {branch_name}")

        # Step 2: Assign VLAN
        with st.spinner("Assigning VLAN..."):
            display_progress("Assigning VLAN to interface", 0.67)
            client.assign_vlan_to_interface(
                interface_id,
                vlan_id,
                branch_name
            )
            st.success(f"✅ {vlan_name} assigned to {interface_name}")

        # Step 3: Create proposed change
        with st.spinner("Creating proposed change..."):
            display_progress("Creating proposed change", 1.0)
            pc = client.create_proposed_change(
                branch=branch_name,
                name=f"VLAN Change: {device_name} {interface_name}",
                description=f"Assign {vlan_name} to {interface_name} on {device_name}"
            )

            # Generate URL
            pc_url = f"{INFRAHUB_UI_URL}/proposed-changes/{pc['id']}"

            display_success("Proposed change created successfully!")
            st.markdown(f"### [🔗 View Proposed Change]({pc_url})")
            st.caption("Click the link above to review and merge the changes in Infrahub.")

    except InfrahubAPIError as e:
        error_msg = str(e).lower()
        if "branch" in error_msg and "create" in error_msg:
            display_error("Branch creation failed", str(e))
        elif "assign" in error_msg or "mutation" in error_msg or "interface" in error_msg:
            display_error(
                "VLAN assignment failed",
                f"{str(e)}\n\nBranch '{branch_name}' was created but assignment failed. "
                f"You can manually complete the assignment in Infrahub."
            )
        elif "proposed" in error_msg or "change" in error_msg:
            display_error(
                "Proposed change creation failed",
                f"{str(e)}\n\nVLAN was assigned in branch '{branch_name}'. "
                f"Please create the proposed change manually in Infrahub."
            )
        else:
            display_error("Workflow failed", str(e))
    except InfrahubConnectionError as e:
        display_error("Connection error", f"Unable to connect to Infrahub: {str(e)}")
    except Exception as e:
        display_error("Unexpected error", str(e))


def main() -> None:
    """Main function to render the VLAN management page."""

    # Display logo in sidebar
    display_logo()

    # Initialize API client (always use "main" branch)
    client = InfrahubClient(
        st.session_state.infrahub_url,
        api_token=INFRAHUB_API_TOKEN or None,
        ui_url=INFRAHUB_UI_URL
    )

    # Page title
    st.title("VLAN Management")
    st.markdown(
        "Modify VLAN assignments on customer-facing ports of leaf switches."
    )

    # Progress indicator in sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📋 Form Progress")
    
    # Initialize progress tracking
    progress_steps = {
        "Location": False,
        "Device": False,
        "Interface": False,
        "VLAN": False
    }

    # Render location selectors
    st.markdown("---")
    location_selections = render_location_selectors(client)
    
    # Update progress
    if location_selections.get("building_id"):
        progress_steps["Location"] = True
    if location_selections.get("device_id"):
        progress_steps["Device"] = True

    # Only proceed if device is selected
    if location_selections.get("device_id"):
        device_id = location_selections["device_id"]

        # Type guard - device_id is guaranteed to be str here due to the if check
        assert device_id is not None, "device_id should not be None after check"

        # Get device name for display
        device_name = None
        for key in st.session_state.keys():
            if key == "device_selector":
                device_name = st.session_state[key]
                break

        if not device_name:
            device_name = "Selected Device"

        st.markdown("---")

        # Render interface selector
        interface_info = render_interface_selector(client, device_id, device_name)

        if interface_info:
            interface_id = interface_info["id"]
            interface_name = interface_info["name"]
            progress_steps["Interface"] = True

            st.markdown("---")
            
            # Display current VLANs
            render_current_vlans(client, interface_id)

            st.markdown("---")
            
            # Render VLAN selector
            vlan_info = render_vlan_selector(client)

            if vlan_info:
                progress_steps["VLAN"] = True
                vlan_id = vlan_info["id"]
                vlan_display_name = f"VLAN {vlan_info['vlan_id']} - {vlan_info['name']}"

                st.markdown("---")
                
                # Submit button
                submit_button = st.button(
                    "Submit VLAN Change",
                    type="primary",
                    help="Create a branch and apply the VLAN change",
                    use_container_width=True
                )

                if submit_button:
                    # Execute workflow
                    execute_vlan_change_workflow(
                        client,
                        device_name,
                        interface_name,
                        interface_id,
                        vlan_id,
                        vlan_display_name
                    )
            else:
                st.info("👆 Select a VLAN above to continue.")
        else:
            st.info("👆 Select an interface above to continue.")
    else:
        st.info("👆 Complete the location selection above to continue.")

    # Display progress in sidebar
    for step, completed in progress_steps.items():
        icon = "✅" if completed else "⬜"
        st.sidebar.markdown(f"{icon} {step}")

    # Display main branch indicator
    st.sidebar.markdown("---")
    st.sidebar.info("**Branch:** main (read-only)")
    st.sidebar.caption("All data is queried from the main branch. Changes will be applied to a new branch.")

    # Footer
    st.markdown("---")
    st.markdown(
        f"Connected to Infrahub at `{st.session_state.infrahub_url}` | "
        f"Branch: `main`"
    )


if __name__ == "__main__":
    main()
