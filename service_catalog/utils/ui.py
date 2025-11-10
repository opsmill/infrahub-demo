"""UI utilities and shared components for the Infrahub Service Catalog."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st


def load_logo() -> str:
    """Load appropriate logo based on Streamlit theme.

    Detects the current Streamlit theme (light or dark mode) and returns
    the path to the appropriate logo file.

    Returns:
        str: Path to the logo file (light or dark version).
    """
    # Detect theme from Streamlit's session state or config
    # Streamlit doesn't expose theme directly, so we check the theme config
    try:
        theme = st.get_option("theme.base")
    except Exception:
        # Default to light theme if detection fails
        theme = "light"

    # Determine logo file based on theme
    if theme == "dark":
        logo_file = "infrahub-hori-dark.svg"
    else:
        logo_file = "infrahub-hori.svg"

    # Construct path to logo in assets directory
    assets_dir = Path(__file__).parent.parent / "assets"
    logo_path = assets_dir / logo_file

    return str(logo_path)


def display_logo() -> None:
    """Display the Infrahub logo above the sidebar navigation.

    Uses st.logo() to place the logo above the page navigation links.
    Automatically selects the appropriate logo (light or dark) based on
    the current Streamlit theme.
    """
    # Get paths for both light and dark logos
    assets_dir = Path(__file__).parent.parent / "assets"
    logo_light = str(assets_dir / "infrahub-hori.svg")
    logo_dark = str(assets_dir / "infrahub-hori-dark.svg")

    # Check if logo files exist
    if os.path.exists(logo_light) and os.path.exists(logo_dark):
        # st.logo() automatically switches between light and dark based on theme
        st.logo(logo_light, icon_image=logo_dark)
    elif os.path.exists(logo_light):
        st.logo(logo_light)
    else:
        # Fallback: display text if logo not found
        st.sidebar.markdown("### Infrahub Service Catalog")


def display_error(message: str, details: Optional[str] = None) -> None:
    """Display an error message with optional details.

    Args:
        message: The main error message to display.
        details: Optional additional details about the error.
    """
    st.error(message)

    if details:
        with st.expander("Error Details"):
            st.code(details, language=None)


def display_success(message: str) -> None:
    """Display a success message.

    Args:
        message: The success message to display.
    """
    st.success(message)


def display_progress(message: str, progress: float) -> None:
    """Display a progress bar with a message.

    Args:
        message: The message to display above the progress bar.
        progress: Progress value between 0.0 and 1.0.
    """
    st.text(message)
    st.progress(progress)


def format_datacenter_table(datacenters: List[Dict[str, Any]]) -> pd.DataFrame:
    """Format datacenter data as a pandas DataFrame for table display.

    Extracts relevant fields from the Infrahub API response and formats
    them into a clean table structure.

    Args:
        datacenters: List of datacenter objects from Infrahub API.

    Returns:
        pd.DataFrame: Formatted DataFrame with columns: Name, Location,
            Description, Strategy, Design.
    """
    if not datacenters:
        return pd.DataFrame(
            columns=["Name", "Location", "Description", "Strategy", "Design"]
        )

    formatted_data = []
    for dc in datacenters:
        # Extract nested values safely
        name = dc.get("name", {}).get("value", "N/A")

        # Location is a relationship (node)
        location_node = dc.get("location", {}).get("node", {})
        location = location_node.get("display_label", "N/A") if location_node else "N/A"

        description = dc.get("description", {}).get("value", "N/A")
        strategy = dc.get("strategy", {}).get("value", "N/A")

        # Design is also a relationship (node)
        design_node = dc.get("design", {}).get("node", {})
        design = (
            design_node.get("name", {}).get("value", "N/A") if design_node else "N/A"
        )

        formatted_data.append(
            {
                "Name": name,
                "Location": location,
                "Description": description,
                "Strategy": strategy,
                "Design": design,
            }
        )

    return pd.DataFrame(formatted_data)


def format_colocation_table(colocations: List[Dict[str, Any]]) -> pd.DataFrame:
    """Format colocation center data as a pandas DataFrame for table display.

    Extracts relevant fields from the Infrahub API response and formats
    them into a clean table structure.

    Args:
        colocations: List of colocation center objects from Infrahub API.

    Returns:
        pd.DataFrame: Formatted DataFrame with relevant columns for
            colocation centers.
    """
    if not colocations:
        return pd.DataFrame(columns=["Name", "Location", "Description", "Provider"])

    formatted_data = []
    for colo in colocations:
        # Extract nested values safely
        name = colo.get("name", {}).get("value", "N/A")

        # Location is a relationship (node)
        location_node = colo.get("location", {}).get("node", {})
        location = location_node.get("display_label", "N/A") if location_node else "N/A"

        description = colo.get("description", {}).get("value", "N/A")
        provider = colo.get("provider", {}).get("value", "N/A")

        formatted_data.append(
            {
                "Name": name,
                "Location": location,
                "Description": description,
                "Provider": provider,
            }
        )

    return pd.DataFrame(formatted_data)
