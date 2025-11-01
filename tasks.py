"""Tasks for the infrahub-demo project."""

import os
import sys
from pathlib import Path
from invoke import task, Context  # type: ignore


INFRAHUB_VERSION = os.getenv("INFRAHUB_VERSION", "stable")
MAIN_DIRECTORY_PATH = Path(__file__).parent

# Download compose file and use with override
def get_compose_command() -> str:
    """Generate docker compose command with override support."""
    override_file = MAIN_DIRECTORY_PATH / "docker-compose.override.yml"
    if override_file.exists():
        return f"curl -s https://infrahub.opsmill.io/{INFRAHUB_VERSION} | docker compose -p infrahub -f - -f {override_file}"
    return f"curl -s https://infrahub.opsmill.io/{INFRAHUB_VERSION} | docker compose -p infrahub -f -"

COMPOSE_COMMAND = get_compose_command()
CURRENT_DIRECTORY = Path(__file__).resolve()
DOCUMENTATION_DIRECTORY = CURRENT_DIRECTORY.parent / "docs"


@task
def start(context: Context) -> None:
    """Start all containers."""
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
