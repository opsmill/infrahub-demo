# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **infrahub-demo**, a comprehensive demonstration of design-driven network automation using [InfraHub](https://docs.infrahub.app). The project showcases composable data center and POP topology generation, configuration management, validation checks, and infrastructure-as-code patterns.

## Package Manager & Environment

- **Package Manager**: `uv` (required for all dependency operations)
- **Python Version**: 3.10, 3.11, or 3.12
- **Setup**: `uv sync` to install all dependencies

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
uv run infrahubctl object load objects/bootstrap --branch main

# Load security data
uv run infrahubctl object load objects/security/ --branch main

# Add demo repository
uv run infrahubctl repository add DEMO https://github.com/opsmill/infrahub-demo.git --read-only

# Load event actions (optional)
uv run infrahubctl object load objects/events/ --branch main
```

### Branch Management
```bash
# Create a new branch
uv run infrahubctl branch create <branch-name>

# Load data to specific branch
uv run infrahubctl object load objects/dc-2 --branch <branch-name>
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
uv run infrahubctl object load objects/bootstrap

# 5. Load security data (optional)
uv run infrahubctl object load objects/security/

# 6. Add repository
uv run infrahubctl repository add DEMO https://github.com/opsmill/infrahub-demo.git --read-only

# 7. Load event actions (optional)
uv run infrahubctl object load objects/events/

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
uv run infrahubctl object load objects/dc-2 --branch my-branch
# Then run generator via InfraHub UI: Actions → Generator Definitions → create_dc
```

## Project Structure Details

- `checks/` - Validation checks for spine, leaf, edge, loadbalancer devices
- `objects/bootstrap/` - Initial data (locations, platforms, roles)
- `objects/dc-2/`, `dc-3.yml`, etc. - Demo scenario data
- `objects/security/` - Security-related demo data
- `objects/cloud_security/` - Cloud security examples
- `objects/events/` - Event action definitions
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
- [Project Discussions](https://github.com/opsmill/infrahub-demo/discussions/)

## Documentation Quality

### Linting and Formatting

When working on documentation files (`.mdx`), always run markdownlint to ensure consistent formatting:

```bash
# Check all documentation files
markdownlint docs/docs/**/*.mdx

# Fix auto-fixable issues
markdownlint docs/docs/**/*.mdx --fix
```

### Common Markdownlint Rules

- **MD032**: Lists must be surrounded by blank lines
- **MD022**: Headings must be surrounded by blank lines
- **MD007**: Use consistent list indentation (4 spaces for nested items)
- **MD009**: No trailing spaces
- **MD031**: Fenced code blocks must be surrounded by blank lines
- **MD040**: Fenced code blocks should specify a language

### Documentation Standards

- Follow the Diataxis framework for content structure
- Use clear, actionable headings for guides
- Include code snippets with language specifications
- Add explanatory callouts (:::tip, :::info, :::warning) for important concepts
- Ensure all lists and code blocks have proper spacing

### Vale Style Guide

When working on documentation, run Vale to ensure consistent style:

```bash
# Run Vale on documentation files (as used in CI)
vale $(find ./docs/docs -type f \( -name "*.mdx" -o -name "*.md" \) )

```

#### Common Vale Issues to Fix

1. **Sentence Case for Headings**
   - Use sentence case for all headings (lowercase except first word and proper nouns)
   - Example: "Understanding the workflow" not "Understanding the Workflow"
   - Exception: Proper nouns like "Infrahub", "GitHub", "Streamlit"

2. **Spelling Exceptions**
   - Add technical terms to `.vale/styles/spelling-exceptions.txt`
   - Common additions: `IPs`, `Gbps`, `Mbps`, `UIs`, `configs`, `auditable`, `idempotently`
   - Keep terms alphabetically sorted in the file

3. **Word Choices**
   - Avoid "simple" and "easy" - use "straightforward" or "clear" instead
   - Use "for example:" instead of "e.g." or "i.e."
   - Keep "configs" as is (don't replace with "configurations")

4. **GitHub Capitalization**
   - Always capitalize as "GitHub" not "github"
   - Note: Vale's branded-terms rule may sometimes false positive on correct usage

### Documentation Writing Guidelines

**Applies to:** All MDX files (`**/*.mdx`)

**Role:** Expert Technical Writer and MDX Generator with:

- Deep understanding of Infrahub and its capabilities
- Expertise in network automation and infrastructure management
- Proficiency in writing structured MDX documents
- Awareness of developer ergonomics

**Documentation Purpose:**

- Guide users through installing, configuring, and using Infrahub in real-world workflows
- Explain concepts and system architecture clearly, including new paradigms introduced by Infrahub
- Support troubleshooting and advanced use cases with actionable, well-organized content
- Enable adoption by offering approachable examples and hands-on guides that lower the learning curve

**Structure:** Follows [Diataxis framework](https://diataxis.fr/)

- **Tutorials** (learning-oriented)
- **How-to guides** (task-oriented)
- **Explanation** (understanding-oriented)
- **Reference** (information-oriented)

**Tone and Style:**

- Professional but approachable: Avoid jargon unless well defined. Use plain language with technical precision
- Concise and direct: Prefer short, active sentences. Reduce fluff
- Informative over promotional: Focus on explaining how and why, not on marketing
- Consistent and structured: Follow a predictable pattern across sections and documents

**For Guides:**

- Use conditional imperatives: "If you want X, do Y. To achieve W, do Z."
- Focus on practical tasks and problems, not the tools themselves
- Address the user directly using imperative verbs: "Configure...", "Create...", "Deploy..."
- Maintain focus on the specific goal without digressing into explanations
- Use clear titles that state exactly what the guide shows how to accomplish

**For Topics:**

- Use a more discursive, reflective tone that invites understanding
- Include context, background, and rationale behind design decisions
- Make connections between concepts and to users' existing knowledge
- Present alternative perspectives and approaches where appropriate
- Use illustrative analogies and examples to deepen understanding

**Terminology and Naming:**

- Always define new terms when first used. Use callouts or glossary links if possible
- Prefer domain-relevant language that reflects the user's perspective (e.g., playbooks, branches, schemas, commits)
- Be consistent: follow naming conventions established by Infrahub's data model and UI

**Reference Files:**

- Documentation guidelines: `docs/docs/development/docs.mdx`
- Vale styles: `.vale/styles/`
- Markdown linting: `.markdownlint.yaml`

### Document Structure Patterns (Following Diataxis)

**How-to Guides Structure (Task-oriented, practical steps):**

```markdown
- Title and Metadata
    - Title should clearly state what problem is being solved (YAML frontmatter)
    - Begin with "How to..." to signal the guide's purpose
    - Optional: Imports for components (e.g., Tabs, TabItem, CodeBlock, VideoPlayer)
- Introduction
    - Brief statement of the specific problem or goal this guide addresses
    - Context or real-world use case that frames the guide
    - Clearly indicate what the user will achieve by following this guide
    - Optional: Links to related topics or more detailed documentation
- Prerequisites / Assumptions
    - What the user should have or know before starting
    - Environment setup or requirements
    - What prior knowledge is assumed
- Step-by-Step Instructions
    - Step 1: [Action/Goal]
        - Clear, actionable instructions focused on the task
        - Code snippets (YAML, GraphQL, shell commands, etc.)
        - Screenshots or images for visual guidance
        - Tabs for alternative methods (e.g., Web UI, GraphQL, Shell/cURL)
        - Notes, tips, or warnings as callouts
    - Step 2: [Action/Goal]
        - Repeat structure as above for each step
    - Step N: [Action/Goal]
        - Continue as needed
- Validation / Verification
    - How to check that the solution worked as expected
    - Example outputs or screenshots
    - Potential failure points and how to address them
- Advanced Usage / Variations
    - Optional: Alternative approaches for different circumstances
    - Optional: How to adapt the solution for related problems
    - Optional: Ways to extend or optimize the solution
- Related Resources
    - Links to related guides, reference materials, or explanation topics
    - Optional: Embedded videos or labs for further learning
```

**Topics Structure (Understanding-oriented, theoretical knowledge):**

```markdown
- Title and Metadata
    - Title should clearly indicate the topic being explained (YAML frontmatter)
    - Consider using "About..." or "Understanding..." in the title
    - Optional: Imports for components (e.g., Tabs, TabItem, CodeBlock, VideoPlayer)
- Introduction
    - Brief overview of what this explanation covers
    - Why this topic matters in the context of Infrahub
    - Questions this explanation will answer
- Main Content Sections
    - Concepts & Definitions
        - Clear explanations of key terms and concepts
        - How these concepts fit into the broader system
    - Background & Context
        - Historical context or evolution of the concept/feature
        - Design decisions and rationale behind implementations
        - Technical constraints or considerations
    - Architecture & Design (if applicable)
        - Diagrams, images, or explanations of structure
        - How components interact or relate to each other
    - Mental Models
        - Analogies and comparisons to help understanding
        - Different ways to think about the topic
    - Connection to Other Concepts
        - How this topic relates to other parts of Infrahub
        - Integration points and relationships
    - Alternative Approaches
        - Different perspectives or methodologies
        - Pros and cons of different approaches
- Further Reading
    - Links to related topics, guides, or reference materials
    - External resources for deeper understanding
```

### Quality and Clarity Checklist

**General Documentation:**

- Content is accurate and reflects the latest version of Infrahub
- Instructions are clear, with step-by-step guidance where needed
- Markdown formatting is correct and compliant with Infrahub's style
- Spelling and grammar are checked

**For Guides:**

- The guide addresses a specific, practical problem or task
- The title clearly indicates what will be accomplished
- Steps follow a logical sequence that maintains flow
- Each step focuses on actions, not explanations
- The guide omits unnecessary details that don't serve the goal
- Validation steps help users confirm their success
- The guide addresses real-world complexity rather than oversimplified scenarios

**For Topics:**

- The explanation is bounded to a specific topic area
- Content provides genuine understanding, not just facts
- Background and context are included to deepen understanding
- Connections are made to related concepts and the bigger picture
- Different perspectives or approaches are acknowledged where relevant
- The content remains focused on explanation without drifting into tutorial or reference material
- The explanation answers "why" questions, not just "what" or "how"
