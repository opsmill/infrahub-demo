"""Validate firewall."""

from typing import Any

from infrahub_sdk.checks import InfrahubCheck

from .common import get_data, validate_interfaces


class CheckLeaf(InfrahubCheck):
    """Check Firewall."""

    query = "leaf_config"

    def validate(self, data: Any) -> None:
        """Validate Leaf."""
        errors: list[str] = []
        warnings: list[str] = []
        data = get_data(data)

        # Validate interfaces - this is critical
        errors.extend(validate_interfaces(data))

        # Check for services - warn if missing but don't fail
        if not data.get("device_services"):
            warnings.append("No services configured on this device")
        else:
            # Only check BGP redundancy if we have services
            redundant_bgp = [
                service.get("name")
                for service in data.get("device_services", [])
                if service.get("typename") == "ServiceBGP"
            ]
            if redundant_bgp and len(redundant_bgp) < 2:
                warnings.append("BGP redundancy not configured - only 1 BGP service found")

        # Log warnings
        for warning in warnings:
            self.log_warning(message=warning)

        # Log errors (these will fail the check)
        for error in errors:
            self.log_error(message=error)
