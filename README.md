# Infrahub demo

[![Ruff][ruff-badge]][ruff-link]
[![Python][python-badge]][python-link]
[![Actions status][github-badge]][github-link]

---

## Requirements

- Python 3.10, 3.11, or 3.12
- [uv](https://github.com/astral-sh/uv) for dependency management
- Docker (for containerlab and some integration tests)

## Features

- Design-driven network automation demo using [InfraHub](https://docs.infrahub.app)
- Example data, schemas, and menu for rapid onboarding
- Scripts for bootstrapping, demo use cases, and CI integration
- Modular structure for easy extension and experimentation

## Project Structure

- [`checks/`](checks/) – Custom validation logic
- [`data/`](data/) – Example data for bootstrapping
- [`generators/`](generators/) – Topology and config generators
- [`menu/`](menu/) – Example menu definition
- [`queries/`](queries/) – GraphQL queries for InfraHub
- [`schemas/`](schemas/) – Base and extension schemas
- [`scripts/`](scripts/) – Helper scripts for automation
- [`templates/`](templates/) – Jinja2 templates for device configs
- [`tests/`](tests/) – Unit, integration, and smoke tests
- [`transforms/`](transforms/) – Python transforms for InfraHub

## Quickstart

### Install the Infrahub SDK

```bash
uv sync
```

### Setup environment variables

```bash
export INFRAHUB_ADDRESS="http://localhost:8000"
export INFRAHUB_API_TOKEN="06438eb2-8019-4776-878c-0941b1f1d1ec"
```

### Start Infrahub

```bash
uv run invoke start
```

### Load initial setup

You can use this script to execute all setup steps:

```bash
./scripts/bootstrap.sh
```

### Manual setup (Alternate)

Load schemas

```bash
uv run infrahubctl schema load schemas
```

Load menu

```bash
uv run infrahubctl menu load menu

```

Load demo data

```bash
uv run infrahubctl object load data/bootstrap
```

Load sample security data

```bash
uv run infrahubctl object load data/security/
````

Add demo repository

```bash
uv run infrahubctl repository add DEMO https://github.com/petercrocker/infrahub-demo-tomek.git --read-only
```

Add event actions

```bash
uv run infrahubctl object load data/events/
````

### Demo 1 - Data Center

In this demo, configuration is generated for a composable data center.

```bash
./scripts/demo.sh dc-2 add-dc2
```

If you would like to process all steps manually, follow these steps:

1. Create branch

    ```bash
    uv run infrahubctl branch create my-branch
    ```

2. Load example design data stored in data/dc-2 file:

    ```bash
    uv run infrahubctl object load data/dc-2.yml --branch my-branch
    ```

   You can review designs in Design Patterns and in Design Elements.
   New deployment should be added into Services -> Topology Deployments -> Data center
3. Change branch to my-branch
4. Go to Actions -> Generator Definitions -> create_dc
5. Select Run -> Selected Targets, select DC-2 and click Run Generator
6. Wait until task is completed
7. Go to the devices and see the generated hosts
8. Go to Propose Changes -> New Proposed change
9. Select my-branch as source branch, add name and Create proposed change
10. Wait until all tasks are completed and check the artifacts/data

If you added event actions steps 4, 5 will be executed automatically.

## CI/CD

This project uses GitHub Actions for continuous integration. All pushes and pull requests are tested for lint, type checks, and unit tests.

## Security & Secrets

- Do not commit real API tokens. Use `.env` or GitHub secrets for sensitive data in production.
- Example tokens in this README are for demo purposes only.

## Troubleshooting

- If you encounter port conflicts, ensure no other service is running on port 8000.
- For dependency issues, run `uv sync` again.
- For Docker/infrahub issues, ensure Docker is running and you have the correct permissions.

## Testing

Run all tests using:

```bash
uv run pytest
```

Or run specific test scripts in the [`tests/`](tests/) directory.

## References

- [InfraHub Documentation](https://docs.infrahub.app)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
