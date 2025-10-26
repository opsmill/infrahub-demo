# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **infrahub-demo**, a comprehensive demonstration of design-driven network automation using [InfraHub](https://docs.infrahub.app). The project showcases composable data center and POP topology generation, configuration management, validation checks, and infrastructure-as-code patterns.

## Package Manager & Environment

- **Package Manager**: `uv` (required for all dependency operations)
- **Python Version**: 3.10, 3.11, or 3.12
- **Setup**: `uv sync` to install dependencies
- **Dev Setup**: `uv sync --group dev` for development tools

## Common Commands

### InfraHub Container Management
```bash
# Start InfraHub (uses invoke tasks)
uv run invoke start

# Stop containers
uv run invoke stop

# Destroy containers (removes volumes)
uv run invoke destroy

# Restart specific component
uv run invoke restart <component>
```

### Schema and Data Loading
```bash
# Load schemas
uv run infrahubctl schema load schemas --branch main

# Load menu
uv run infrahubctl menu load menu --branch main

# Load bootstrap data
uv run infrahubctl object load data/bootstrap --branch main

# Load security data
uv run infrahubctl object load data/security/ --branch main

# Add demo repository
uv run infrahubctl repository add DEMO https://github.com/petercrocker/infrahub-demo-tomek.git --read-only

# Load event actions (optional)
uv run infrahubctl object load data/events/ --branch main
```

### Branch Management
```bash
# Create a new branch
uv run infrahubctl branch create <branch-name>

# Load data to specific branch
uv run infrahubctl object load data/dc-2 --branch <branch-name>
```

### Testing and Validation
```bash
# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -vv

# Run specific test file
uv run pytest tests/unit/test_cloud_security_mock.py

# Run integration tests
uv run pytest tests/integration/

# Run all quality checks (ruff, mypy, pytest)
uv run invoke validate
```

### Code Quality
```bash
# Format and lint code
uv run ruff check . --fix

# Type checking
uv run mypy .

# Full validation suite
uv run invoke validate
```

## High-Level Architecture

### Component Hierarchy

This project follows InfraHub's SDK pattern with five core component types:

1. **Schemas** (`schemas/`) - Define data models, relationships, and constraints
   - `base/` - Core models (DCIM, IPAM, Location, Topology)
   - `extensions/` - Feature-specific extensions
   - Loaded via: `uv run infrahubctl schema load schemas`

2. **Generators** (`generators/`) - Create infrastructure topology programmatically
   - Inherit from `InfrahubGenerator`
   - Triggered by InfraHub events or manual execution
   - Examples: `generate_dc.py` (data center), `generate_pop.py` (point of presence)

3. **Transforms** (`transforms/`) - Convert InfraHub data to device configurations
   - Inherit from `InfrahubTransform`
   - Use GraphQL queries to fetch data
   - Render Jinja2 templates with device-specific logic
   - Examples: `leaf.py`, `spine.py`, `edge.py`, `loadbalancer.py`

4. **Checks** (`checks/`) - Validate configurations and connectivity
   - Inherit from `InfrahubCheck`
   - Run validation logic and log errors/warnings
   - Examples: `spine.py`, `leaf.py`, `edge.py`

5. **Templates** (`templates/`) - Jinja2 templates for device configurations
   - Used by transforms to generate final configs
   - Organized by device type

### Data Flow

```
Schema Definition → Data Loading → Generator Execution → Transform Processing → Configuration Generation
                                         ↓
                                   Validation Checks
```

### Configuration Hub (.infrahub.yml)

All components are registered in `.infrahub.yml`:
- `jinja2_transforms` - Template-based transforms
- `python_transforms` - Python-based transforms
- `generator_definitions` - Topology generators
- `check_definitions` - Validation checks
- `artifact_definitions` - Output artifact definitions
- `queries` - GraphQL query registry

## Code Quality Requirements

### Type Hints (MANDATORY)
All functions must have complete type hints:
```python
from typing import Any, Dict, List, Optional

async def process_data(data: Dict[str, Any], device_name: str) -> List[str]:
    """Process device data and return configuration lines."""
    return []
```

### Testing (MANDATORY)
Every new functionality must have corresponding tests:
- Unit tests in `tests/unit/`
- Integration tests in `tests/integration/`
- Use `unittest.mock` for mocking external dependencies
- Test both success and failure scenarios

### Code Style
- Format with `ruff` before committing
- Pass `mypy` type checking
- Follow PascalCase for classes, snake_case for functions/variables
- Add docstrings for all classes and functions

## InfraHub SDK Patterns

### Generator Pattern
```python
from infrahub_sdk.generators import InfrahubGenerator

class MyTopologyGenerator(InfrahubGenerator):
    async def generate(self, data: dict) -> None:
        """Generate topology based on design data."""
        # Query data, create devices, interfaces, connections
        pass
```

### Transform Pattern
```python
from infrahub_sdk.transforms import InfrahubTransform
from typing import Any

class MyTransform(InfrahubTransform):
    query = "my_config_query"  # GraphQL query name

    async def transform(self, data: Any) -> Any:
        """Transform InfraHub data to device configuration."""
        return self.render_template(template="my_template.j2", data=data)
```

### Check Pattern
```python
from infrahub_sdk.checks import InfrahubCheck
from typing import Any

class MyCheck(InfrahubCheck):
    query = "my_validation_query"

    async def check(self, data: Any) -> None:
        """Validate device configuration."""
        if not self.is_valid(data):
            self.log_error("Validation failed", data)
```

## Schema Conventions

### Naming Conventions
- **Nodes**: PascalCase (e.g., `LocationBuilding`, `DcimGenericDevice`)
- **Attributes**: snake_case (e.g., `device_type`, `ip_address`)
- **Relationships**: snake_case (e.g., `parent_location`, `connected_interfaces`)
- **Namespaces**: PascalCase (e.g., `Dcim`, `Ipam`, `Service`, `Design`)

### Schema Structure
```yaml
nodes:
  - name: MyDevice
    namespace: Dcim
    description: "Device description"
    inherit_from:
      - DcimGenericDevice
    attributes:
      - name: custom_field
        kind: Text
        optional: true
        order_weight: 1000
    relationships:
      - name: location
        peer: LocationBuilding
        cardinality: one
        optional: false
```

## Environment Variables

Required environment variables (can be set in `.env`):
```bash
INFRAHUB_ADDRESS="http://localhost:8000"
INFRAHUB_API_TOKEN="06438eb2-8019-4776-878c-0941b1f1d1ec"
```

Note: The token above is a demo token for local development only.

## Bootstrap Process

The complete setup sequence:
```bash
# 1. Start InfraHub
uv run invoke start

# 2. Load schemas
uv run infrahubctl schema load schemas

# 3. Load menu
uv run infrahubctl menu load menu

# 4. Load bootstrap data
uv run infrahubctl object load data/bootstrap

# 5. Load security data (optional)
uv run infrahubctl object load data/security/

# 6. Add repository
uv run infrahubctl repository add DEMO https://github.com/petercrocker/infrahub-demo-tomek.git --read-only

# 7. Load event actions (optional)
uv run infrahubctl object load data/events/

# Or use the bootstrap script
./scripts/bootstrap.sh
```

## Demo Scenarios

### Data Center Demo
```bash
# Automated approach
./scripts/demo.sh design dc-2

# Manual approach
uv run infrahubctl branch create my-branch
uv run infrahubctl object load data/dc-2 --branch my-branch
# Then run generator via InfraHub UI: Actions → Generator Definitions → create_dc
```

## Project Structure Details

- `checks/` - Validation checks for spine, leaf, edge, loadbalancer devices
- `data/bootstrap/` - Initial data (locations, platforms, roles)
- `data/dc-2/`, `dc-3.yml`, etc. - Demo scenario data
- `data/security/` - Security-related demo data
- `data/cloud_security/` - Cloud security examples
- `data/events/` - Event action definitions
- `generators/` - Topology generators (DC, POP, segment)
- `generators/common.py` - Shared generator utilities
- `generators/schema_protocols.py` - Type protocols for schemas
- `menu/` - InfraHub menu definitions
- `queries/config/` - Configuration queries
- `queries/topology/` - Topology queries
- `queries/validation/` - Validation queries
- `schemas/base/` - Base schema models
- `schemas/extensions/` - Extended schemas
- `scripts/bootstrap.sh` - Complete setup script
- `scripts/demo.sh` - Demo execution script
- `templates/` - Jinja2 configuration templates
- `transforms/` - Python transform implementations
- `tests/conftest.py` - Pytest fixtures and configuration
- `tests/unit/` - Unit tests
- `tests/integration/` - Integration tests
- `tasks.py` - Invoke task definitions

## GraphQL Query Patterns

Queries are defined in `queries/` and referenced by name in transforms/checks:
```graphql
query GetDeviceConfig($device_name: String!) {
  DcimGenericDevice(name__value: $device_name) {
    edges {
      node {
        id
        name { value }
        interfaces {
          edges {
            node {
              name { value }
              description { value }
            }
          }
        }
      }
    }
  }
}
```

## Common Pitfalls

1. **Forgetting to sync dependencies**: Always run `uv sync` after pulling changes
2. **Missing type hints**: All functions require complete type annotations
3. **Untested code**: Every feature must have unit tests
4. **Schema conflicts**: Check for naming conflicts when extending schemas
5. **Incorrect inheritance**: Ensure proper `inherit_from` usage in schemas
6. **Missing .infrahub.yml entries**: Register all generators/transforms/checks

## Resources

- [InfraHub Documentation](https://docs.infrahub.app)
- [InfraHub SDK Documentation](https://docs.infrahub.app/python-sdk/)
- [Project Discussions](https://github.com/t0m3kz/infrahub-demo/discussions/)
