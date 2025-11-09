"""Tasks for the infrahub-demo project."""

import os
import sys
from pathlib import Path
from invoke import task, Context  # type: ignore


INFRAHUB_VERSION = os.getenv("INFRAHUB_VERSION", "stable")
INFRAHUB_ENTERPRISE = os.getenv("INFRAHUB_ENTERPRISE", "false").lower() == "true"
MAIN_DIRECTORY_PATH = Path(__file__).parent


# Download compose file and use with override
def get_compose_command() -> str:
    """Generate docker compose command with override support."""
    # Determine the base URL based on edition
    if INFRAHUB_ENTERPRISE:
        base_url = f"https://infrahub.opsmill.io/enterprise/{INFRAHUB_VERSION}"
    else:
        base_url = f"https://infrahub.opsmill.io/{INFRAHUB_VERSION}"

    override_file = MAIN_DIRECTORY_PATH / "docker-compose.override.yml"
    if override_file.exists():
        return (
            f"curl -s {base_url} | docker compose -p infrahub -f - -f {override_file}"
        )
    return f"curl -s {base_url} | docker compose -p infrahub -f -"


COMPOSE_COMMAND = get_compose_command()
CURRENT_DIRECTORY = Path(__file__).resolve()
DOCUMENTATION_DIRECTORY = CURRENT_DIRECTORY.parent / "docs"


@task(name="list")
def list_tasks(context: Context) -> None:
    """List all available invoke tasks with descriptions."""
    # Import sys and inspect to get the current module
    import inspect
    current_module = inspect.getmodule(inspect.currentframe())

    tasks_info = []

    # Get all task objects from the current module
    for name, obj in inspect.getmembers(current_module):
        # Check if the object is a task (has __wrapped__ or is a Task instance)
        if hasattr(obj, '__wrapped__') or (hasattr(obj, '__class__') and 'Task' in obj.__class__.__name__):
            # Get the display name (check if task has a custom name)
            display_name = getattr(obj, 'name', name)
            # Remove leading underscore from function names if present
            if display_name.startswith('_'):
                continue
            # Get the first line of the docstring as description
            if obj.__doc__:
                description = obj.__doc__.strip().split('\n')[0]
            else:
                description = "No description available"
            tasks_info.append((display_name, description))

    # Sort by task name
    tasks_info.sort(key=lambda x: x[0])

    # Print header
    print("\nAvailable tasks:\n")

    # Calculate max task name length for alignment
    max_name_len = max(len(name) for name, _ in tasks_info) if tasks_info else 0

    # Print each task
    for name, desc in tasks_info:
        print(f"  {name.ljust(max_name_len)}  {desc}")

    print()


@task
def info(context: Context) -> None:
    """Show current Infrahub configuration."""
    edition = "Enterprise" if INFRAHUB_ENTERPRISE else "Community"
    print(f"Infrahub Edition: {edition}")
    print(f"Version: {INFRAHUB_VERSION}")
    print(f"Command: {COMPOSE_COMMAND}")


@task
def start(context: Context) -> None:
    """Start all containers."""
    edition = "Enterprise" if INFRAHUB_ENTERPRISE else "Community"
    print(f"Starting Infrahub {edition} ({INFRAHUB_VERSION})...")
    context.run(f"{COMPOSE_COMMAND} up -d")


@task(optional=["schema", "branch"])
def load_schema(
    context: Context, schema: str = "./schemas/", branch: str = "main"
) -> None:
    """Load the schemas from the given path."""
    context.run(f"infrahubctl schema load {schema} --branch {branch}")


@task(optional=["branch"])
def load_data(
    context: Context, name: str = "bootstrap.py", branch: str = "main"
) -> None:
    """Load the data from the given path."""
    context.run(f"infrahubctl run bootstrap/{name} --branch {branch}")


@task(optional=["branch"])
def load_menu(context: Context, menu: str = "menu", branch: str = "main") -> None:
    """Load the menu from the given path."""
    context.run(f"infrahubctl menu load {menu} --branch {branch}")


@task(optional=["branch"])
def load_objects(
    context: Context, path: str = "objects/bootstrap/", branch: str = "main"
) -> None:
    """Load objects from the given path."""
    context.run(f"infrahubctl object load {path} --branch {branch}")


@task(optional=["branch"])
def bootstrap(context: Context, branch: str = "main") -> None:
    """Run the complete bootstrap process (schemas, menu, data, security, repository)."""
    context.run(f"./scripts/bootstrap.sh {branch}")


@task(optional=["branch"], name="demo-dc-arista")
def demo_dc_arista(context: Context, branch: str = "add-dc3") -> None:
    """Create branch and load Arista DC demo topology."""
    print(f"Creating branch: {branch}")
    context.run(f"uv run infrahubctl branch create {branch}")
    print(f"Loading DC Arista topology to branch: {branch}")
    context.run(f"uv run infrahubctl object load objects/dc-arista-s.yml --branch {branch}")
    print(f"✓ DC Arista topology loaded to branch '{branch}'")


@task(optional=["branch", "topology"])
def containerlab(context: Context, branch: str = "add-dc3", topology: str = "DC-3") -> None:
    """Generate configs and deploy containerlab topology."""
    print(f"Generating configurations from branch: {branch}")
    context.run(f"uv run scripts/get_configs.py --branch {branch}")

    topology_file = f"generated-configs/clab/{topology}.clab.yml"
    print(f"\nDeploying containerlab topology: {topology_file}")
    context.run(f"sudo -E containerlab deploy -t {topology_file}")
    print(f"✓ Containerlab topology '{topology}' deployed successfully")


@task
def destroy(context: Context) -> None:
    """Destroy all containers."""
    context.run(f"{COMPOSE_COMMAND} down -v")


@task
def stop(context: Context) -> None:
    """Stop all containers."""
    context.run(f"{COMPOSE_COMMAND} down")


@task
def restart(context: Context, component: str = "") -> None:
    """Stop all containers."""
    if component:
        context.run(f"{COMPOSE_COMMAND} restart {component}")
        return

    context.run(f"{COMPOSE_COMMAND} restart")


@task
def run_tests(context: Context) -> None:
    """Run all tests."""
    context.run("pytest -vv tests")


@task
def validate(context: Context) -> None:
    """Run all code quality tests."""
    context.run("ruff check . --fix")
    context.run("mypy .")
    context.run("pytest -vv tests")


@task
def format(context: Context) -> None:
    """Run RUFF to format all Python files."""

    exec_cmds = ["ruff format .", "ruff check . --fix"]
    with context.cd(MAIN_DIRECTORY_PATH):
        for cmd in exec_cmds:
            context.run(cmd)


@task
def lint_yaml(context: Context) -> None:
    """Run Linter to check all Python files."""
    print(" - Check code with yamllint")
    exec_cmd = "yamllint ."
    with context.cd(MAIN_DIRECTORY_PATH):
        context.run(exec_cmd)


@task
def lint_mypy(context: Context) -> None:
    """Run Linter to check all Python files."""
    print(" - Check code with mypy")
    exec_cmd = "mypy --show-error-codes ."
    with context.cd(MAIN_DIRECTORY_PATH):
        context.run(exec_cmd)


@task
def lint_ruff(context: Context) -> None:
    """Run Linter to check all Python files."""
    print(" - Check code with ruff")
    exec_cmd = "ruff check ."
    with context.cd(MAIN_DIRECTORY_PATH):
        context.run(exec_cmd)


@task(name="lint")
def lint_all(context: Context) -> None:
    """Run all linters."""
    lint_yaml(context)
    lint_ruff(context)
    lint_mypy(context)


@task(name="docs")
def docs_build(context: Context) -> None:
    """Build documentation website."""
    exec_cmd = "npm run build"

    with context.cd(DOCUMENTATION_DIRECTORY):
        output = context.run(exec_cmd)

    if output and output.exited != 0:
        sys.exit(-1)
