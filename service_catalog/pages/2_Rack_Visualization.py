"""Infrahub Service Catalog - Rack Visualization Page.

This page provides a visual representation of physical racks and the devices
mounted within them, similar to NetBox's rack diagram implementation.
"""

import streamlit as st

from typing import Any, Dict, List

from utils import (
    DEFAULT_BRANCH,
    INFRAHUB_ADDRESS,
    INFRAHUB_API_TOKEN,
    INFRAHUB_UI_URL,
    InfrahubClient,
    display_error,
    display_logo,
)
from utils.api import (
    InfrahubAPIError,
    InfrahubConnectionError,
    InfrahubGraphQLError,
    InfrahubHTTPError,
)
from utils.rack import generate_rack_html


# Configure page layout and title
st.set_page_config(
    page_title="Rack Visualization - Infrahub Service Catalog",
    page_icon="🗄️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session state
if "selected_branch" not in st.session_state:
    st.session_state.selected_branch = DEFAULT_BRANCH

if "infrahub_url" not in st.session_state:
    st.session_state.infrahub_url = INFRAHUB_ADDRESS


def render_rack_diagram(rack: Dict[str, Any], devices: List[Dict[str, Any]]) -> None:
    """Render a single rack diagram with devices.

    Generates HTML visualization of the rack and displays it using Streamlit.

    Args:
        rack: LocationRack object dictionary
        devices: List of DcimPhysicalDevice objects in this rack
    """
    # Generate HTML for rack diagram with Infrahub UI URL and branch
    rack_html = generate_rack_html(
        rack, 
        devices, 
        base_url=INFRAHUB_UI_URL,
        branch=st.session_state.selected_branch
    )

    # Display using st.markdown with unsafe_allow_html
    st.markdown(rack_html, unsafe_allow_html=True)

    # Display device count and details
    device_count = len(devices)
    if device_count > 0:
        # Show device details for debugging
        device_names = [d.get("name", {}).get("value", "Unknown") for d in devices]
        device_positions = [d.get("position", {}).get("value", "No pos") for d in devices]
        
        st.caption(f"{device_count} device(s)")
        
        # Debug info in expander
        with st.expander("Device Details"):
            for i, device in enumerate(devices):
                name = device.get("name", {}).get("value", "Unknown")
                pos = device.get("position", {}).get("value", "N/A")
                height = device.get("height", {}).get("value", "N/A")
                st.text(f"• {name} - Position: U{pos}, Height: {height}U")
    else:
        st.caption("Empty rack")


def render_rack_grid(client: InfrahubClient, row_id: str, branch: str) -> None:
    """Render grid of rack diagrams for the selected row.

    Fetches all racks for the row and displays them in a responsive grid layout.
    For each rack, fetches associated devices and renders a rack diagram.

    Args:
        client: InfrahubClient instance
        row_id: Selected LocationRow ID
        branch: Selected branch name
    """
    try:
        with st.spinner("Loading racks..."):
            racks = client.get_racks_by_row(row_id, branch)

        if not racks:
            st.info("No racks found in the selected row.")
            return

        st.markdown(f"### Racks ({len(racks)} found)")

        # Display loading indicator while fetching devices
        with st.spinner("Loading devices..."):
            # Fetch devices for all racks
            rack_devices = {}
            for rack in racks:
                try:
                    devices = client.get_devices_by_rack(rack["id"], branch)
                    rack_devices[rack["id"]] = devices
                except (InfrahubAPIError, InfrahubConnectionError) as e:
                    st.warning(
                        f"Failed to load devices for rack {rack['name']['value']}: {str(e)}"
                    )
                    rack_devices[rack["id"]] = []

        # Render racks in columns (max 4 per row)
        num_cols = min(len(racks), 4)
        cols = st.columns(num_cols)

        for idx, rack in enumerate(racks):
            with cols[idx % num_cols]:
                try:
                    devices = rack_devices.get(rack["id"], [])
                    render_rack_diagram(rack, devices)
                except Exception as e:
                    st.error(
                        f"Failed to render rack {rack['name']['value']}: {str(e)}"
                    )

    except InfrahubConnectionError as e:
        display_error("Unable to connect to Infrahub", str(e))
    except InfrahubHTTPError as e:
        display_error(
            f"HTTP Error {e.status_code} while fetching racks",
            f"{str(e)}\n\nResponse: {e.response_text}",
        )
    except InfrahubGraphQLError as e:
        display_error("GraphQL Error while fetching racks", str(e))
    except InfrahubAPIError as e:
        display_error("Failed to load racks", str(e))
    except Exception as e:
        display_error("Unexpected error while loading racks", str(e))


def render_row_selector(client: InfrahubClient, branch: str) -> str:
    """Render LocationRow dropdown selector.

    Fetches all LocationRow objects from Infrahub and displays them in a dropdown.
    Caches the row list in session state to avoid repeated queries.

    Args:
        client: InfrahubClient instance
        branch: Selected branch name

    Returns:
        Selected row ID or empty string if no selection
    """
    # Cache key for rows based on branch
    cache_key = f"location_rows_{branch}"

    # Fetch rows if not cached or branch changed
    if cache_key not in st.session_state:
        with st.spinner("Loading location rows..."):
            try:
                st.session_state[cache_key] = client.get_location_rows(branch)
            except (InfrahubConnectionError, InfrahubHTTPError, InfrahubGraphQLError) as e:
                display_error("Failed to load location rows", str(e))
                return ""
            except Exception as e:
                display_error("Unexpected error loading location rows", str(e))
                return ""

    rows = st.session_state[cache_key]

    if not rows:
        st.warning(
            f"No location rows found in branch '{branch}'. "
            "Please create LocationRow objects in Infrahub."
        )
        return ""

    # Prepare row options
    row_names = [row.get("name", {}).get("value", "Unknown") for row in rows]
    row_map = {
        row.get("name", {}).get("value", "Unknown"): row.get("id")
        for row in rows
    }

    # Display row selector
    selected_row_name = st.selectbox(
        "Select Location Row",
        options=row_names,
        help="Choose a row to view its racks and devices",
        key="row_selector",
    )

    # Return selected row ID
    return row_map.get(selected_row_name, "")


def main() -> None:
    """Main function to render the rack visualization page."""

    # Display logo in sidebar
    display_logo()

    # Initialize API client
    client = InfrahubClient(
        st.session_state.infrahub_url, api_token=INFRAHUB_API_TOKEN or None
    )

    # Page title
    st.title("Rack Visualization")
    st.markdown(
        "View physical rack layouts and device placement within your infrastructure."
    )

    # Branch selector in sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("Branch Selection")

    try:
        # Fetch branches (cache in session state to avoid repeated API calls)
        if "branches" not in st.session_state:
            with st.spinner("Loading branches..."):
                st.session_state.branches = client.get_branches()

        branches = st.session_state.branches

        if branches:
            # Extract branch names
            branch_names = [branch["name"] for branch in branches]

            # Find index of currently selected branch
            try:
                default_index = branch_names.index(st.session_state.selected_branch)
            except ValueError:
                default_index = 0
                st.session_state.selected_branch = (
                    branch_names[0] if branch_names else DEFAULT_BRANCH
                )

            # Display branch selector dropdown
            selected_branch = st.sidebar.selectbox(
                "Select Branch",
                options=branch_names,
                index=default_index,
                help="Choose a branch to view its infrastructure resources",
                key="branch_selector_rack_viz",
            )

            # Update session state if branch changed
            if selected_branch != st.session_state.selected_branch:
                st.session_state.selected_branch = selected_branch
                # Clear cached row data when branch changes
                keys_to_clear = [
                    key for key in st.session_state.keys() if key.startswith("location_rows_")
                ]
                for key in keys_to_clear:
                    del st.session_state[key]
                st.rerun()
        else:
            st.sidebar.warning("No branches found")

    except InfrahubConnectionError as e:
        display_error("Unable to connect to Infrahub", str(e))
        st.stop()
    except InfrahubHTTPError as e:
        display_error(
            f"HTTP Error {e.status_code}", f"{str(e)}\n\nResponse: {e.response_text}"
        )
        st.stop()
    except InfrahubGraphQLError as e:
        display_error("GraphQL Error", str(e))
        st.stop()
    except Exception as e:
        display_error("Unexpected error while fetching branches", str(e))
        st.stop()

    # Display current branch info
    st.sidebar.info(f"Current Branch: **{st.session_state.selected_branch}**")

    # Row selector
    st.markdown("---")
    selected_row_id = render_row_selector(
        client, st.session_state.selected_branch
    )

    if not selected_row_id:
        st.info("👆 Select a location row above to view racks.")
        return

    # Render rack grid
    st.markdown("---")
    render_rack_grid(client, selected_row_id, st.session_state.selected_branch)

    # Footer
    st.markdown("---")
    st.markdown(
        f"Connected to Infrahub at `{st.session_state.infrahub_url}` | "
        f"Branch: `{st.session_state.selected_branch}`"
    )


if __name__ == "__main__":
    main()
