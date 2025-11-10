"""Infrahub Service Catalog - Landing Page.

This is the main landing page for the Infrahub Service Catalog application.
It displays lists of Data Centers and Colocation Centers with branch selection capability.
"""

import streamlit as st

from utils import (
    DEFAULT_BRANCH,
    INFRAHUB_ADDRESS,
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
    client = InfrahubClient(st.session_state.infrahub_url)

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
            dc_df = format_datacenter_table(datacenters)
            st.dataframe(dc_df, width="stretch", hide_index=True)
            st.caption(f"Found {len(datacenters)} data center(s)")
        else:
            st.info("No data centers found in this branch.")

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
