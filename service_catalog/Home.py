"""Infrahub Service Catalog - Landing Page.

This is the main landing page for the Infrahub Service Catalog application.
It displays lists of Data Centers and Colocation Centers with branch selection capability.
"""

import streamlit as st

from utils import (
    DEFAULT_BRANCH,
    INFRAHUB_ADDRESS,
    INFRAHUB_API_TOKEN,
    INFRAHUB_UI_URL,
    InfrahubClient,
    display_error,
    display_logo,
    format_colocation_table,
    format_datacenter_table,
)
from utils.api import InfrahubConnectionError, InfrahubHTTPError, InfrahubGraphQLError


# Configure page layout and title
st.set_page_config(
    page_title="Infrahub Service Catalog",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"Get Help": None, "Report a bug": None, "About": None},
)

# Initialize session state
if "selected_branch" not in st.session_state:
    st.session_state.selected_branch = DEFAULT_BRANCH

if "infrahub_url" not in st.session_state:
    st.session_state.infrahub_url = INFRAHUB_ADDRESS


def main() -> None:
    """Main function to render the landing page."""

    # Display logo in sidebar
    display_logo()

    # Initialize API client
    client = InfrahubClient(
        st.session_state.infrahub_url,
        api_token=INFRAHUB_API_TOKEN or None
    )

    # Page title
    st.title("Infrahub Service Catalog")
    st.markdown(
        "Welcome to the Infrahub Service Catalog. View and manage your infrastructure resources."
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
                key="branch_selector",
            )

            # Update session state if branch changed
            if selected_branch != st.session_state.selected_branch:
                st.session_state.selected_branch = selected_branch
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

    # Main content area
    st.markdown("---")

    # Data Centers section
    st.header("Data Centers")

    try:
        with st.spinner(
            f"Loading data centers from branch '{st.session_state.selected_branch}'..."
        ):
            datacenters = client.get_objects(
                "TopologyDataCenter", st.session_state.selected_branch
            )

        if datacenters:
            # Format and display datacenter table
            dc_df = format_datacenter_table(
                datacenters,
                base_url=INFRAHUB_UI_URL,
                branch=st.session_state.selected_branch
            )
            st.dataframe(
                dc_df,
                width="stretch",
                hide_index=True,
                column_config={
                    "Link": st.column_config.LinkColumn(
                        "View in Infrahub",
                        help="Open this datacenter in the Infrahub UI",
                        display_text="Open"
                    )
                }
            )
            st.caption(f"Found {len(datacenters)} data center(s)")
        else:
            st.info("No data centers found in this branch.")

            # Show debug info if on a non-main branch
            if st.session_state.selected_branch != "main":
                with st.expander("🔍 Debug Information"):
                    st.markdown("**Query Details:**")
                    st.code(f"Branch: {st.session_state.selected_branch}")
                    st.code("Object Type: TopologyDataCenter")
                    st.code(f"Infrahub Address: {client.base_url}")

                    # Check for proposed changes
                    try:
                        pcs = client.get_proposed_changes(st.session_state.selected_branch)
                        if pcs:
                            st.markdown("**Proposed Changes on this branch:**")
                            for pc in pcs:
                                pc_name = pc.get("name", {}).get("value", "Unknown")
                                pc_state = pc.get("state", {}).get("value", "Unknown")
                                st.write(f"- {pc_name} (State: {pc_state})")
                        else:
                            st.write("No proposed changes found on this branch.")
                    except Exception as e:
                        st.write(f"Could not fetch proposed changes: {e}")

                    # Check what other objects exist on this branch
                    st.markdown("**Other objects on this branch:**")
                    try:
                        # Query for generic devices
                        device_query = """
                        query {
                          DcimGenericDevice {
                            count
                            edges {
                              node {
                                id
                                name { value }
                                __typename
                              }
                            }
                          }
                        }
                        """
                        result = client.execute_graphql(device_query, branch=st.session_state.selected_branch)
                        device_count = result.get("DcimGenericDevice", {}).get("count", 0)
                        st.write(f"- DcimGenericDevice: {device_count} object(s)")

                        if device_count > 0:
                            devices = result.get("DcimGenericDevice", {}).get("edges", [])
                            for device in devices[:5]:  # Show first 5
                                dev_name = device.get("node", {}).get("name", {}).get("value", "Unknown")
                                st.write(f"  - {dev_name}")
                    except Exception as e:
                        st.write(f"Error checking other objects: {e}")

    except InfrahubConnectionError as e:
        display_error("Unable to connect to Infrahub", str(e))
    except InfrahubHTTPError as e:
        display_error(
            f"HTTP Error {e.status_code} while fetching data centers",
            f"{str(e)}\n\nResponse: {e.response_text}",
        )
    except InfrahubGraphQLError as e:
        display_error("GraphQL Error while fetching data centers", str(e))
    except Exception as e:
        display_error("Unexpected error while fetching data centers", str(e))

    # Colocation Centers section
    st.markdown("---")
    st.header("Colocation Centers")

    try:
        with st.spinner(
            f"Loading colocation centers from branch '{st.session_state.selected_branch}'..."
        ):
            colocations = client.get_objects(
                "TopologyColocationCenter", st.session_state.selected_branch
            )

        if colocations:
            # Format and display colocation table
            colo_df = format_colocation_table(colocations)
            st.dataframe(colo_df, width="stretch", hide_index=True)
            st.caption(f"Found {len(colocations)} colocation center(s)")
        else:
            st.info("No colocation centers found in this branch.")

    except InfrahubConnectionError as e:
        display_error("Unable to connect to Infrahub", str(e))
    except InfrahubHTTPError as e:
        display_error(
            f"HTTP Error {e.status_code} while fetching colocation centers",
            f"{str(e)}\n\nResponse: {e.response_text}",
        )
    except InfrahubGraphQLError as e:
        display_error("GraphQL Error while fetching colocation centers", str(e))
    except Exception as e:
        display_error("Unexpected error while fetching colocation centers", str(e))

    # Footer
    st.markdown("---")
    st.markdown(
        f"Connected to Infrahub at `{st.session_state.infrahub_url}` | "
        f"Branch: `{st.session_state.selected_branch}`"
    )


if __name__ == "__main__":
    main()
