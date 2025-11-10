"""Configuration management for the Infrahub Service Catalog."""

import os
from typing import Final

# Load environment variables
INFRAHUB_ADDRESS: Final[str] = os.getenv("INFRAHUB_ADDRESS", "http://localhost:8000")
STREAMLIT_PORT: Final[int] = int(os.getenv("STREAMLIT_PORT", "8501"))
DEFAULT_BRANCH: Final[str] = os.getenv("DEFAULT_BRANCH", "main")
GENERATOR_WAIT_TIME: Final[int] = int(os.getenv("GENERATOR_WAIT_TIME", "60"))
API_TIMEOUT: Final[int] = int(os.getenv("API_TIMEOUT", "30"))
API_RETRY_COUNT: Final[int] = int(os.getenv("API_RETRY_COUNT", "3"))


def validate_config() -> None:
    """Validate configuration values.

    Raises:
        ValueError: If any configuration value is invalid.
    """
    if not INFRAHUB_ADDRESS:
        raise ValueError("INFRAHUB_ADDRESS must be set")

    if STREAMLIT_PORT <= 0 or STREAMLIT_PORT > 65535:
        raise ValueError(
            f"STREAMLIT_PORT must be between 1 and 65535, got {STREAMLIT_PORT}"
        )

    if not DEFAULT_BRANCH:
        raise ValueError("DEFAULT_BRANCH must be set")

    if GENERATOR_WAIT_TIME < 0:
        raise ValueError(
            f"GENERATOR_WAIT_TIME must be non-negative, got {GENERATOR_WAIT_TIME}"
        )

    if API_TIMEOUT <= 0:
        raise ValueError(f"API_TIMEOUT must be positive, got {API_TIMEOUT}")

    if API_RETRY_COUNT < 0:
        raise ValueError(f"API_RETRY_COUNT must be non-negative, got {API_RETRY_COUNT}")
