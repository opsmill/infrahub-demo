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

    progress_bar = st.progress(0)
    status_text = st.empty()

    for i in range(duration + 1):
        # Calculate progress (0.0 to 1.0)
        progress = i / duration

        # Update progress bar
        progress_bar.progress(progress)

        # Update status text
        remaining = duration - i
        status_text.text(
            f"Waiting for generator to complete... {remaining} seconds remaining"
        )

        # Wait 1 second (except on last iteration)
        if i < duration:
            time.sleep(1)

    # Clear status text and show completion
    status_text.text("Generator wait complete!")
    progress_bar.empty()
    status_text.empty()


def handle_dc_creation(client: InfrahubClient, form_data: Dict[str, Any]) -> None:
    """Orchestrate the DC creation workflow.

    This function handles the complete workflow:
    1. Validate form inputs
    2. Generate branch name
    3. Create branch
    4. Create datacenter
    5. Wait for generator
    6. Create proposed change
    7. Display success message with PC URL

    Args:
        client: InfrahubClient instance
        form_data: Dictionary containing form data
    """
    dc_name = form_data["name"]

    # Generate branch name: "add-{dc_name}" (lowercase, replace spaces with hyphens)
    branch_name = f"add-{dc_name.lower().replace(' ', '-')}"

    branch_created = False
    dc_created = False

    try:
        # Step 1: Create branch
        with st.status("Creating branch...", expanded=True) as status:
            try:
                st.write(f"Creating branch: {branch_name}")
                branch = client.create_branch(branch_name, from_branch="main")
                branch_created = True
                st.write(f"✓ Branch created: {branch['name']}")
                status.update(label="Branch created!", state="complete")
            except InfrahubConnectionError as e:
                status.update(label="Branch creation failed!", state="error")
                display_error(
                    "Unable to connect to Infrahub",
                    f"Failed to create branch '{branch_name}'.\n\n{str(e)}",
                )
                st.stop()
            except InfrahubHTTPError as e:
                status.update(label="Branch creation failed!", state="error")
                display_error(
                    f"HTTP Error {e.status_code} while creating branch",
                    f"Failed to create branch '{branch_name}'.\n\n{str(e)}\n\nResponse: {e.response_text}",
                )
                st.stop()
            except InfrahubGraphQLError as e:
                status.update(label="Branch creation failed!", state="error")
                display_error(
                    "GraphQL Error while creating branch",
                    f"Failed to create branch '{branch_name}'.\n\n{str(e)}",
                )
                st.stop()
            except InfrahubAPIError as e:
                status.update(label="Branch creation failed!", state="error")
                display_error(
                    "Failed to create branch", f"Branch: {branch_name}\n\n{str(e)}"
                )
                st.stop()

        # Step 2: Prepare datacenter data
        # Need to get design ID - for now we'll use the design name as ID
        # In production, you'd query Infrahub for the actual design ID
        dc_data = {
            "name": form_data["name"],
            "location": form_data["location"],
            "description": form_data.get("description", ""),
            "strategy": form_data["strategy"],
            "design": form_data[
                "design"
            ],  # This should be an ID, but we'll use name for now
            "emulation": form_data.get("emulation", False),
            "provider": form_data["provider"],
            "management_subnet": {
                "data": {
                    "prefix": form_data["management_subnet"]["prefix"],
                    "status": form_data["management_subnet"]["status"],
                    "role": form_data["management_subnet"]["role"],
                }
            },
            "customer_subnet": {
                "data": {
                    "prefix": form_data["customer_subnet"]["prefix"],
                    "status": form_data["customer_subnet"]["status"],
                    "role": form_data["customer_subnet"]["role"],
                }
            },
            "technical_subnet": {
                "data": {
                    "prefix": form_data["technical_subnet"]["prefix"],
                    "status": form_data["technical_subnet"]["status"],
                    "role": form_data["technical_subnet"]["role"],
                }
            },
            "member_of_groups": ["topologies_dc", "topologies_clab"],
        }

        # Step 3: Create datacenter
        with st.status("Loading data...", expanded=True) as status:
            try:
                st.write(f"Creating datacenter: {dc_name}")
                dc = client.create_datacenter(branch_name, dc_data)
                dc_created = True
                st.write(f"✓ Datacenter created: {dc['name']['value']}")
                status.update(label="Data loaded!", state="complete")
            except InfrahubConnectionError as e:
                status.update(label="Data loading failed!", state="error")
                display_error(
                    "Unable to connect to Infrahub",
                    f"Failed to load datacenter data to branch '{branch_name}'.\n\n"
                    f"{str(e)}\n\n"
                    f"The branch '{branch_name}' was created but is empty. "
                    f"You may need to manually investigate or delete this branch.",
                )
                st.stop()
            except InfrahubHTTPError as e:
                status.update(label="Data loading failed!", state="error")
                display_error(
                    f"HTTP Error {e.status_code} while loading data",
                    f"Failed to load datacenter data to branch '{branch_name}'.\n\n"
                    f"{str(e)}\n\nResponse: {e.response_text}\n\n"
                    f"The branch '{branch_name}' was created but is empty. "
                    f"You may need to manually investigate or delete this branch.",
                )
                st.stop()
            except InfrahubGraphQLError as e:
                status.update(label="Data loading failed!", state="error")
                display_error(
                    "GraphQL Error while loading data",
                    f"Failed to load datacenter data to branch '{branch_name}'.\n\n"
                    f"{str(e)}\n\n"
                    f"The branch '{branch_name}' was created but is empty. "
                    f"You may need to manually investigate or delete this branch.",
                )
                st.stop()
            except InfrahubAPIError as e:
                status.update(label="Data loading failed!", state="error")
                display_error(
                    "Failed to load datacenter data",
                    f"Branch: {branch_name}\n\n{str(e)}\n\n"
                    f"The branch '{branch_name}' was created but is empty. "
                    f"You may need to manually investigate or delete this branch.",
                )
                st.stop()

        # Step 4: Wait for generator
        with st.status("Waiting for generator...", expanded=True) as status:
            st.write(
                f"Waiting {GENERATOR_WAIT_TIME} seconds for generator to complete..."
            )
            wait_for_generator(GENERATOR_WAIT_TIME)
            st.write("✓ Generator wait complete")
            status.update(label="Generator complete!", state="complete")

        # Step 5: Create proposed change
        with st.status("Creating Proposed Change...", expanded=True) as status:
            try:
                pc_name = f"Add Data Center: {dc_name}"
                pc_description = f"Proposed change to add new data center {dc_name} in {form_data['location']}"
                st.write(f"Creating Proposed Change: {pc_name}")
                pc = client.create_proposed_change(branch_name, pc_name, pc_description)
                pc_id = pc["id"]
                pc_url = client.get_proposed_change_url(pc_id)
                st.write("✓ Proposed Change created")
                status.update(label="Proposed Change created!", state="complete")
            except (
                InfrahubConnectionError,
                InfrahubHTTPError,
                InfrahubGraphQLError,
                InfrahubAPIError,
            ) as e:
                status.update(label="Proposed Change creation failed!", state="error")
                display_error(
                    "Failed to create Proposed Change",
                    f"The datacenter '{dc_name}' was created successfully in branch '{branch_name}', "
                    f"but the Proposed Change could not be created.\n\n"
                    f"Error: {str(e)}\n\n"
                    f"You can manually create a Proposed Change for branch '{branch_name}' in the Infrahub UI.",
                )
                # Don't stop - show partial success
                st.warning(
                    f"⚠️ Data Center '{dc_name}' was created in branch '{branch_name}', "
                    f"but you'll need to manually create a Proposed Change."
                )
                return

        # Step 6: Display success message
        st.markdown("---")
        display_success(f"Data Center '{dc_name}' created successfully!")

        st.markdown(f"""
        ### Next Steps
        
        Your data center has been created in branch `{branch_name}` and a Proposed Change has been created.
        
        **Proposed Change URL:**  
        [{pc_url}]({pc_url})
        
        Click the link above to review and merge your changes in Infrahub.
        """)

    except Exception as e:
        # Catch any unexpected errors
        display_error(
            "Unexpected error during DC creation",
            f"An unexpected error occurred: {str(e)}\n\n"
            f"Branch created: {branch_created}\n"
            f"Datacenter created: {dc_created}\n\n"
            f"If the branch was created, you may need to manually investigate or delete branch '{branch_name}'.",
        )


def main() -> None:
    """Main function to render the Create DC page."""

    # Display logo in sidebar
    display_logo()

    # Page title
    st.title("Create Data Center")
    st.markdown("Fill in the form below to create a new Data Center in Infrahub.")

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
            )

            location = st.text_input(
                "Location *",
                placeholder="e.g., London",
                help="Physical location of the data center",
            )

            strategy = st.selectbox(
                "Strategy *",
                options=["ospf-ibgp", "isis-ibgp", "ospf-ebgp"],
                help="Routing strategy for the data center",
            )

            provider = st.selectbox(
                "Provider *",
                options=["Technology Partner", "Cloud Provider", "Colocation"],
                help="Infrastructure provider",
            )

        with col2:
            description = st.text_area(
                "Description",
                placeholder="e.g., London Data Center",
                help="Optional description of the data center",
            )

            design = st.selectbox(
                "Design *",
                options=[
                    "PHYSICAL DC ARISTA S",
                    "PHYSICAL DC CISCO S",
                    "PHYSICAL DC JUNIPER S",
                    "PHYSICAL DC SONIC S",
                ],
                help="Network design template",
            )

            emulation = st.checkbox(
                "Emulation", value=True, help="Enable emulation mode"
            )

        # Subnet configuration
        st.markdown("---")
        st.subheader("Subnet Configuration")

        # Management Subnet
        st.markdown("**Management Subnet**")
        col1, col2, col3 = st.columns(3)

        with col1:
            mgmt_prefix = st.text_input(
                "Prefix *",
                placeholder="e.g., 172.20.4.0/24",
                key="mgmt_prefix",
                help="Management subnet prefix in CIDR notation",
            )

        with col2:
            mgmt_status = st.selectbox(
                "Status *",
                options=["active", "reserved", "deprecated"],
                key="mgmt_status",
                help="Status of the management subnet",
            )

        with col3:
            mgmt_role = st.selectbox(
                "Role *",
                options=["management", "infrastructure", "services"],
                key="mgmt_role",
                help="Role of the management subnet",
            )

        # Customer Subnet
        st.markdown("**Customer Subnet**")
        col1, col2, col3 = st.columns(3)

        with col1:
            cust_prefix = st.text_input(
                "Prefix *",
                placeholder="e.g., 10.4.0.0/16",
                key="cust_prefix",
                help="Customer subnet prefix in CIDR notation",
            )

        with col2:
            cust_status = st.selectbox(
                "Status *",
                options=["active", "reserved", "deprecated"],
                key="cust_status",
                help="Status of the customer subnet",
            )

        with col3:
            cust_role = st.selectbox(
                "Role *",
                options=["supernet", "customer", "services"],
                key="cust_role",
                help="Role of the customer subnet",
            )

        # Technical Subnet
        st.markdown("**Technical Subnet**")
        col1, col2, col3 = st.columns(3)

        with col1:
            tech_prefix = st.text_input(
                "Prefix *",
                placeholder="e.g., 1.4.0.0/24",
                key="tech_prefix",
                help="Technical subnet prefix in CIDR notation",
            )

        with col2:
            tech_status = st.selectbox(
                "Status *",
                options=["active", "reserved", "deprecated"],
                key="tech_status",
                help="Status of the technical subnet",
            )

        with col3:
            tech_role = st.selectbox(
                "Role *",
                options=["loopback", "infrastructure", "services"],
                key="tech_role",
                help="Role of the technical subnet",
            )

        # Submit button
        st.markdown("---")
        submitted = st.form_submit_button(
            "Create Data Center", type="primary", use_container_width=True
        )

        if submitted:
            # Validate required fields
            errors = []

            if not name:
                errors.append("Name is required")
            if not location:
                errors.append("Location is required")
            if not strategy:
                errors.append("Strategy is required")
            if not design:
                errors.append("Design is required")
            if not provider:
                errors.append("Provider is required")
            if not mgmt_prefix:
                errors.append("Management subnet prefix is required")
            if not mgmt_status:
                errors.append("Management subnet status is required")
            if not mgmt_role:
                errors.append("Management subnet role is required")
            if not cust_prefix:
                errors.append("Customer subnet prefix is required")
            if not cust_status:
                errors.append("Customer subnet status is required")
            if not cust_role:
                errors.append("Customer subnet role is required")
            if not tech_prefix:
                errors.append("Technical subnet prefix is required")
            if not tech_status:
                errors.append("Technical subnet status is required")
            if not tech_role:
                errors.append("Technical subnet role is required")

            if errors:
                display_error(
                    "Form validation failed",
                    "\n".join(f"• {error}" for error in errors),
                )
            else:
                # Store form data in session state for processing
                form_data = {
                    "name": name,
                    "location": location,
                    "description": description,
                    "strategy": strategy,
                    "design": design,
                    "emulation": emulation,
                    "provider": provider,
                    "management_subnet": {
                        "prefix": mgmt_prefix,
                        "status": mgmt_status,
                        "role": mgmt_role,
                    },
                    "customer_subnet": {
                        "prefix": cust_prefix,
                        "status": cust_status,
                        "role": cust_role,
                    },
                    "technical_subnet": {
                        "prefix": tech_prefix,
                        "status": tech_status,
                        "role": tech_role,
                    },
                }

                # Initialize API client
                client = InfrahubClient(st.session_state.infrahub_url)

                # Execute DC creation workflow
                handle_dc_creation(client, form_data)


if __name__ == "__main__":
    main()
