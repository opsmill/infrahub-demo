"""Infrahub Service Catalog - Create Data Center Page.

This page provides a form-based interface for creating new Data Centers in Infrahub.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
import yaml

from utils import (
    DEFAULT_BRANCH,
    GENERATOR_WAIT_TIME,
    INFRAHUB_ADDRESS,
    INFRAHUB_API_TOKEN,
    InfrahubClient,
    display_error,
    display_logo,
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
    page_title="Create Data Center - Infrahub Service Catalog",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session state
if "selected_branch" not in st.session_state:
    st.session_state.selected_branch = DEFAULT_BRANCH

if "infrahub_url" not in st.session_state:
    st.session_state.infrahub_url = INFRAHUB_ADDRESS

if "form_data" not in st.session_state:
    st.session_state.form_data = {}

if "dc_template" not in st.session_state:
    st.session_state.dc_template = None


def load_dc_template() -> Optional[Dict[str, Any]]:
    """Load and parse the DC template YAML file.

    Reads the /objects/dc-arista-s.yml file (mounted volume) and parses it
    to extract the field structure for the DC creation form.

    Returns:
        Dictionary containing the parsed template data, or None if file not found.
    """
    template_path = Path("/objects/dc-arista-s.yml")

    try:
        with open(template_path, "r") as f:
            template_data = yaml.safe_load(f)
        return template_data
    except FileNotFoundError:
        st.error(f"Template file not found at {template_path}")
        return None
    except yaml.YAMLError as e:
        st.error(f"Error parsing template YAML: {e}")
        return None
    except Exception as e:
        st.error(f"Unexpected error loading template: {e}")
        return None


def extract_field_options(template: Dict[str, Any], field_name: str) -> List[str]:
    """Extract dropdown options from the template for a specific field.

    Args:
        template: Parsed template dictionary
        field_name: Name of the field to extract options for

    Returns:
        List of valid options for the field, or empty list if not found.
    """
    try:
        # Navigate to the data section
        spec = template.get("spec", {})
        data_list = spec.get("data", [])

        if not data_list:
            return []

        # Get the first data item as a reference
        first_item = data_list[0]

        # Extract the field value
        field_value = first_item.get(field_name)

        if field_value is not None:
            # For simple fields, return the value as a single option
            # In a real scenario, you might want to query Infrahub for valid options
            return [str(field_value)]

        return []
    except Exception:
        return []


def wait_for_generator(duration: int = 60) -> None:
    """Wait for the Infrahub generator to complete with a progress indicator.

    Displays a progress bar that updates every second during the wait period.
    This allows the generator event to complete before creating a Proposed Change.

    Args:
        duration: Wait duration in seconds (default: 60)
    """
    import time

    progress_bar = st.progress(0, text="Starting generator wait...")
    time_display = st.empty()

    for i in range(duration + 1):
        # Calculate progress (0.0 to 1.0)
        progress = i / duration
        percentage = int(progress * 100)

        # Update progress bar with text
        progress_bar.progress(
            progress,
            text=f"Generator running... {percentage}% complete"
        )

        # Update status text
        remaining = duration - i
        elapsed = i

        # Show time information with better formatting
        time_display.markdown(
            f"**Time:** {elapsed}s elapsed / {remaining}s remaining ({duration}s total)"
        )

        # Wait 1 second (except on last iteration)
        if i < duration:
            time.sleep(1)

    # Show completion
    progress_bar.progress(1.0, text="✓ Generator wait complete!")
    time_display.markdown("**✓ Generator processing time completed**")

    # Brief pause to show completion
    time.sleep(1)

    # Clean up
    progress_bar.empty()
    time_display.empty()


def initialize_dc_creation_state(form_data: Dict[str, Any]) -> None:
    """Initialize session state for DC creation workflow."""
    dc_name = form_data["name"]
    branch_name = f"add-{dc_name.lower().replace(' ', '-')}"

    st.session_state.dc_creation = {
        "active": True,
        "step": 1,
        "dc_name": dc_name,
        "branch_name": branch_name,
        "form_data": form_data,
        "branch_created": False,
        "dc_created": False,
        "pc_created": False,
        "error": None,
        "pc_url": None,
    }


def render_progress_tracker() -> None:
    """Render the progress tracker based on current state."""
    if "dc_creation" not in st.session_state or not st.session_state.dc_creation.get("active"):
        return

    state = st.session_state.dc_creation
    current_step = state["step"]

    steps = [
        "Creating branch",
        "Creating datacenter",
        "Waiting for generator",
        "Creating proposed change",
        "Complete"
    ]

    progress_md = "### Progress\n\n"
    for i, step_name in enumerate(steps, 1):
        if i < current_step:
            progress_md += f"✓ {step_name}\n\n"
        elif i == current_step:
            progress_md += f"⏳ **{step_name}**\n\n"
        else:
            progress_md += f"⏸️ {step_name}\n\n"

    st.markdown(progress_md)


def execute_dc_creation_step(client: InfrahubClient) -> None:
    """Execute the current step of DC creation workflow."""
    state = st.session_state.dc_creation
    step = state["step"]
    branch_name = state["branch_name"]
    dc_name = state["dc_name"]
    form_data = state["form_data"]

    try:
        if step == 1:
            # Step 1: Create branch
            with st.status("Creating branch...", expanded=True) as status:
                st.write(f"Creating branch: {branch_name}")
                branch = client.create_branch(branch_name, from_branch="main")
                st.write(f"✓ Branch created: {branch['name']}")
                status.update(label="Branch created!", state="complete")
                state["branch_created"] = True
                state["step"] = 2
                st.rerun()

        elif step == 2:
            # Step 2: Create datacenter
            dc_data = {
                "name": form_data["name"],
                "location": form_data["location"],
                "description": form_data.get("description", ""),
                "strategy": form_data["strategy"],
                "design": form_data["design"],
                "emulation": form_data.get("emulation", False),
                "provider": form_data["provider"],
                "management_subnet": form_data["management_subnet"],
                "customer_subnet": form_data["customer_subnet"],
                "technical_subnet": form_data["technical_subnet"],
                "member_of_groups": form_data.get("member_of_groups", ["topologies_dc", "topologies_clab"]),
            }

            with st.status("Creating datacenter...", expanded=True) as status:
                st.write(f"Creating datacenter: {dc_name}")
                dc = client.create_datacenter(branch_name, dc_data)
                st.write(f"✓ Datacenter created: {dc['name']['value']}")
                status.update(label="Datacenter created!", state="complete")
                state["dc_created"] = True
                state["step"] = 3
                st.rerun()

        elif step == 3:
            # Step 3: Wait for generator
            with st.status("Waiting for generator...", expanded=True) as status:
                st.write(f"Waiting {GENERATOR_WAIT_TIME} seconds for generator to complete...")
                wait_for_generator(GENERATOR_WAIT_TIME)
                st.write("✓ Generator wait complete")
                status.update(label="Generator complete!", state="complete")
                state["step"] = 4
                st.rerun()

        elif step == 4:
            # Step 4: Create proposed change
            with st.status("Creating Proposed Change...", expanded=True) as status:
                pc_name = f"Add Data Center: {dc_name}"
                pc_description = f"Proposed change to add new data center {dc_name} in {form_data.get('location_name', form_data['location'])}"
                st.write(f"Creating Proposed Change: {pc_name}")
                pc = client.create_proposed_change(branch_name, pc_name, pc_description)
                pc_id = pc["id"]
                pc_url = client.get_proposed_change_url(pc_id)
                st.write("✓ Proposed Change created")
                status.update(label="Proposed Change created!", state="complete")
                state["pc_created"] = True
                state["pc_url"] = pc_url
                state["step"] = 5
                st.rerun()

        elif step == 5:
            # Step 5: Complete - show success message
            state["active"] = False
            st.markdown("---")
            display_success(f"Data Center '{dc_name}' created successfully!")

            st.markdown(f"""
            ### Next Steps

            Your data center has been created in branch `{branch_name}` and a Proposed Change has been created.

            **Proposed Change URL:**
            [{state['pc_url']}]({state['pc_url']})

            Click the link above to review and merge your changes in Infrahub.
            """)

    except (InfrahubConnectionError, InfrahubHTTPError, InfrahubGraphQLError, InfrahubAPIError) as e:
        state["error"] = str(e)
        state["active"] = False

        if step == 1:
            display_error("Failed to create branch", f"Branch: {branch_name}\n\n{str(e)}")
        elif step == 2:
            display_error(
                "Failed to create datacenter",
                f"The branch '{branch_name}' was created but the datacenter could not be created.\n\n{str(e)}"
            )
        elif step == 4:
            display_error(
                "Failed to create Proposed Change",
                f"The datacenter '{dc_name}' was created successfully in branch '{branch_name}', "
                f"but the Proposed Change could not be created.\n\n{str(e)}\n\n"
                f"You can manually create a Proposed Change for branch '{branch_name}' in the Infrahub UI."
            )
            st.warning(
                f"⚠️ Data Center '{dc_name}' was created in branch '{branch_name}', "
                f"but you'll need to manually create a Proposed Change."
            )


def handle_dc_creation(client: InfrahubClient, form_data: Dict[str, Any]) -> None:
    """Initialize the DC creation workflow.

    Args:
        client: InfrahubClient instance
        form_data: Dictionary containing form data
    """
    initialize_dc_creation_state(form_data)
    st.rerun()


def main() -> None:
    """Main function to render the Create DC page."""

    # Display logo in sidebar
    display_logo()

    # Page title
    st.title("Create Data Center")

    # Check if DC creation is in progress
    dc_creation_active = "dc_creation" in st.session_state and st.session_state.dc_creation.get("active")

    # Normal form display
    if not dc_creation_active:
        st.markdown("Fill in the form below to create a new Data Center in Infrahub.")
    else:
        st.info("📋 Datacenter creation in progress... Form is read-only during execution.")

    # Initialize API client to fetch locations
    client = InfrahubClient(
        st.session_state.infrahub_url,
        api_token=INFRAHUB_API_TOKEN or None
    )

    # Fetch locations (cache in session state)
    if "locations" not in st.session_state:
        with st.spinner("Loading locations..."):
            try:
                st.session_state.locations = client.get_locations()
            except Exception as e:
                display_error(
                    "Unable to load locations",
                    f"Failed to fetch LocationMetro objects from Infrahub.\n\n{str(e)}",
                )
                st.stop()

    # Fetch providers (cache in session state)
    if "providers" not in st.session_state:
        with st.spinner("Loading providers..."):
            try:
                st.session_state.providers = client.get_providers()
            except Exception as e:
                display_error(
                    "Unable to load providers",
                    f"Failed to fetch OrganizationProvider objects from Infrahub.\n\n{str(e)}",
                )
                st.stop()

    # Fetch designs (cache in session state)
    if "designs" not in st.session_state:
        with st.spinner("Loading designs..."):
            try:
                st.session_state.designs = client.get_designs()
            except Exception as e:
                display_error(
                    "Unable to load designs",
                    f"Failed to fetch DesignTopologyDesign objects from Infrahub.\n\n{str(e)}",
                )
                st.stop()

    # Fetch active prefixes (always refresh, don't cache)
    with st.spinner("Loading active prefixes..."):
        try:
            st.session_state.active_prefixes = client.get_active_prefixes()
            if not st.session_state.active_prefixes:
                st.warning(
                    "⚠️ No active IpamPrefix objects found in Infrahub. "
                    "You'll need to create some prefixes with status='active' before creating a datacenter. "
                    "Querying branch: main"
                )
        except Exception as e:
            display_error(
                "Unable to load active prefixes",
                f"Failed to fetch active IpamPrefix objects from Infrahub.\n\n{str(e)}",
            )
            st.stop()

    # Load DC template (cache in session state)
    if st.session_state.dc_template is None:
        with st.spinner("Loading DC template..."):
            st.session_state.dc_template = load_dc_template()

    # Check if template loaded successfully
    if st.session_state.dc_template is None:
        display_error(
            "Unable to load DC template",
            "The template file /objects/dc-arista-s.yml could not be loaded. "
            "Please ensure the objects directory is properly mounted.",
        )
        st.stop()

    # DC Creation Form
    st.markdown("---")

    with st.form("dc_creation_form"):
        st.subheader("Data Center Information")

        # Required fields
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input(
                "Name *",
                placeholder="e.g., DC-4",
                help="Unique name for the data center",
                disabled=dc_creation_active,
            )

            # Prepare location options from fetched locations
            location_names = [loc.get("name", {}).get("value") for loc in st.session_state.locations]
            location_map = {
                loc.get("name", {}).get("value"): loc.get("id")
                for loc in st.session_state.locations
            }

            location_name = st.selectbox(
                "Location *",
                options=location_names,
                help="Physical location of the data center",
                disabled=dc_creation_active,
            )

            # Get the location ID for the selected name
            location_id = location_map.get(location_name) if location_name else None

            strategy = st.selectbox(
                "Strategy *",
                options=["ospf-ibgp", "isis-ibgp", "ospf-ebgp"],
                help="Routing strategy for the data center",
                disabled=dc_creation_active,
            )

            # Prepare provider options
            provider_names = [p.get("name", {}).get("value") for p in st.session_state.providers]
            provider_map = {
                p.get("name", {}).get("value"): p.get("id")
                for p in st.session_state.providers
            }

            provider_name = st.selectbox(
                "Provider *",
                options=provider_names,
                help="Infrastructure provider",
                disabled=dc_creation_active,
            )

            # Get the provider ID for the selected name
            provider_id = provider_map.get(provider_name) if provider_name else None

        with col2:
            description = st.text_area(
                "Description",
                placeholder="e.g., London Data Center",
                help="Optional description of the data center",
                disabled=dc_creation_active,
            )

            # Prepare design options
            design_names = [d.get("name", {}).get("value") for d in st.session_state.designs]
            design_map = {
                d.get("name", {}).get("value"): d.get("id")
                for d in st.session_state.designs
            }

            design_name = st.selectbox(
                "Design *",
                options=design_names,
                help="Network design template",
                disabled=dc_creation_active,
            )

            # Get the design ID for the selected name
            design_id = design_map.get(design_name) if design_name else None

            emulation = st.checkbox(
                "Emulation", value=True, help="Enable emulation mode", disabled=dc_creation_active
            )

        # Subnet configuration
        st.markdown("---")
        st.subheader("Subnet Configuration")
        st.markdown("Select existing active prefixes for each subnet type")

        # Prepare prefix options - display as "prefix"
        prefix_options = {}
        prefix_map = {}
        for prefix in st.session_state.active_prefixes:
            prefix_value = prefix.get("prefix", {}).get("value")
            prefix_id = prefix.get("id")
            display_text = prefix_value
            prefix_options[display_text] = prefix_id
            prefix_map[prefix_id] = {"prefix": prefix_value}

        option_list = list(prefix_options.keys()) if prefix_options else ["No active prefixes available"]

        # Management Subnet
        st.markdown("**Management Subnet**")
        mgmt_prefix_display = st.selectbox(
            "Select Management Prefix *",
            options=option_list,
            key="mgmt_prefix_select",
            help="Select an active prefix for management subnet",
            disabled=dc_creation_active or not prefix_options,
        )
        mgmt_prefix_id = prefix_options.get(mgmt_prefix_display) if prefix_options else None

        # Customer Subnet
        st.markdown("**Customer Subnet**")
        cust_prefix_display = st.selectbox(
            "Select Customer Prefix *",
            options=option_list,
            key="cust_prefix_select",
            help="Select an active prefix for customer subnet",
            disabled=dc_creation_active or not prefix_options,
        )
        cust_prefix_id = prefix_options.get(cust_prefix_display) if prefix_options else None

        # Technical Subnet
        st.markdown("**Technical Subnet**")
        tech_prefix_display = st.selectbox(
            "Select Technical Prefix *",
            options=option_list,
            key="tech_prefix_select",
            help="Select an active prefix for technical subnet",
            disabled=dc_creation_active or not prefix_options,
        )
        tech_prefix_id = prefix_options.get(tech_prefix_display) if prefix_options else None

        # Submit button
        st.markdown("---")
        submitted = st.form_submit_button(
            "Create Data Center", type="primary", use_container_width=True, disabled=dc_creation_active
        )

        if submitted:
            # Validate required fields
            errors = []

            if not name:
                errors.append("Name is required")
            if not location_id:
                errors.append("Location is required")
            if not strategy:
                errors.append("Strategy is required")
            if not design_id:
                errors.append("Design is required")
            if not provider_id:
                errors.append("Provider is required")
            if not mgmt_prefix_id:
                errors.append("Management subnet is required")
            if not cust_prefix_id:
                errors.append("Customer subnet is required")
            if not tech_prefix_id:
                errors.append("Technical subnet is required")

            if errors:
                display_error(
                    "Form validation failed",
                    "\n".join(f"• {error}" for error in errors),
                )
            else:
                # Store form data in session state for processing
                form_data = {
                    "name": name,
                    "location": location_id,
                    "location_name": location_name,  # Store name for display in messages
                    "description": description,
                    "strategy": strategy,
                    "design": design_id,
                    "emulation": emulation,
                    "provider": provider_id,
                    "management_subnet": mgmt_prefix_id,
                    "customer_subnet": cust_prefix_id,
                    "technical_subnet": tech_prefix_id,
                    "member_of_groups": ["topologies_dc", "topologies_clab"],
                }

                # Execute DC creation workflow (reuse the client from initialization)
                handle_dc_creation(client, form_data)

    # After the form, check if DC creation is in progress and show progress at bottom
    if dc_creation_active:
        st.markdown("---")
        st.markdown("## 🔄 Datacenter Creation Progress")

        # Execute current step
        execute_dc_creation_step(client)

        # Render progress tracker at the bottom
        st.markdown("---")
        render_progress_tracker()


if __name__ == "__main__":
    main()
