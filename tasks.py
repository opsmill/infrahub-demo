"""Tasks for the infrahub-demo project."""

import os
import sys
import time
from pathlib import Path
from invoke import task, Context  # type: ignore
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich import box

console = Console()


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
    import inspect
    current_module = inspect.getmodule(inspect.currentframe())

    tasks_info = []

    # Get all task objects from the current module
    for name, obj in inspect.getmembers(current_module):
        if hasattr(obj, '__wrapped__') or (hasattr(obj, '__class__') and 'Task' in obj.__class__.__name__):
            display_name = getattr(obj, 'name', name)
            if display_name.startswith('_'):
                continue
            if obj.__doc__:
                description = obj.__doc__.strip().split('\n')[0]
            else:
                description = "No description available"
            tasks_info.append((display_name, description))

    # Sort by task name
    tasks_info.sort(key=lambda x: x[0])

    # Create a Rich table
    table = Table(
        title="Available Invoke Tasks",
        box=box.SIMPLE,
        show_header=True,
        header_style="bold cyan"
    )
    table.add_column("Task", style="green", no_wrap=True)
    table.add_column("Description", style="white")

    for name, desc in tasks_info:
        table.add_row(name, desc)

    console.print()
    console.print(table)
    console.print()


@task
def info(context: Context) -> None:
    """Show current Infrahub configuration."""
    edition = "Enterprise" if INFRAHUB_ENTERPRISE else "Community"

    info_panel = Panel(
        f"[cyan]Edition:[/cyan] {edition}\n"
        f"[cyan]Version:[/cyan] {INFRAHUB_VERSION}\n"
        f"[cyan]Command:[/cyan] [dim]{COMPOSE_COMMAND}[/dim]",
        title="[bold]Infrahub Configuration[/bold]",
        border_style="blue",
        box=box.SIMPLE
    )
    console.print()
    console.print(info_panel)
    console.print()


@task
def start(context: Context) -> None:
    """Start all containers."""
    edition = "Enterprise" if INFRAHUB_ENTERPRISE else "Community"
    console.print()
    console.print(Panel(
        f"[green]Starting Infrahub {edition}[/green] [dim]({INFRAHUB_VERSION})[/dim]",
        border_style="green",
        box=box.SIMPLE
    ))
    context.run(f"{COMPOSE_COMMAND} up -d")
    console.print("[green]✓[/green] Infrahub started successfully")


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


@task(optional=["branch"], name="bootstrap-bash")
def bootstrap_bash(context: Context, branch: str = "main") -> None:
    """Run the complete bootstrap process (bash version)."""
    console.print()
    console.print(Panel(
        f"[bold blue]Infrahub Bootstrap (Bash)[/bold blue]\n"
        f"[dim]Branch:[/dim] {branch}\n"
        f"[dim]This will load schemas, menu, bootstrap data, security, and repository[/dim]",
        border_style="blue",
        box=box.SIMPLE
    ))
    console.print()
    context.run(f"./scripts/bootstrap.sh {branch}")
    console.print()
    console.print("[green]✓[/green] Bootstrap completed successfully!")
    console.print()


@task(optional=["branch"], name="bootstrap")
def bootstrap_py(context: Context, branch: str = "main") -> None:
    """Run the complete bootstrap process (Python version with Rich UI)."""
    context.run(f"uv run python scripts/bootstrap.py --branch {branch}", pty=True)


@task(optional=["branch"], name="demo-dc-arista")
def demo_dc_arista(context: Context, branch: str = "add-dc3") -> None:
    """Create branch and load Arista DC demo topology."""
    console.print()
    console.print(Panel(
        f"[bold cyan]Arista Data Center Demo[/bold cyan]\n"
        f"[dim]Branch:[/dim] {branch}",
        border_style="cyan",
        box=box.SIMPLE
    ))

    console.print(f"\n[cyan]→[/cyan] Creating branch: [bold]{branch}[/bold]")
    context.run(f"uv run infrahubctl branch create {branch}")

    console.print(f"\n[cyan]→[/cyan] Loading DC Arista topology to branch: [bold]{branch}[/bold]")
    context.run(f"uv run infrahubctl object load objects/dc-arista-s.yml --branch {branch}")

    console.print(f"\n[green]✓[/green] DC Arista topology loaded to branch '[bold green]{branch}[/bold green]'")

    # Wait for generator to finish creating the data
    console.print("\n[yellow]→[/yellow] Waiting for generator to complete data creation...")
    wait_seconds = 60  # Wait 60 seconds for generator to process

    with Progress(
        SpinnerColumn(spinner_name="dots12", style="bold bright_yellow"),
        TextColumn("[progress.description]{task.description}", style="bold white"),
        BarColumn(
            bar_width=40,
            style="yellow",
            complete_style="bright_green",
            finished_style="bold bright_green",
            pulse_style="bright_yellow"
        ),
        TextColumn("[bold bright_cyan]{task.percentage:>3.0f}%"),
        TextColumn("•", style="dim"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("⏳ Generator processing", total=wait_seconds)
        for _ in range(wait_seconds):
            time.sleep(1)
            progress.update(task, advance=1)

    console.print("[green]✓[/green] Generator processing complete")

    # Create proposed change
    console.print(f"\n[bright_magenta]→[/bright_magenta] Creating proposed change for branch '[bold]{branch}[/bold]'...")
    context.run(f"uv run python scripts/create_proposed_change.py --branch {branch}", pty=True)

    console.print()


@task(optional=["branch"], name="create-pc")
def create_proposed_change(context: Context, branch: str = "add-dc3") -> None:
    """Create an Infrahub Proposed Change for a branch."""
    context.run(f"uv run python scripts/create_proposed_change.py --branch {branch}", pty=True)


@task(optional=["branch", "topology"])
def containerlab(context: Context, branch: str = "add-dc3", topology: str = "DC-3") -> None:
    """Generate configs and deploy containerlab topology."""
    console.print()
    console.print(Panel(
        f"[bold magenta]Containerlab Deployment[/bold magenta]\n"
        f"[dim]Branch:[/dim] {branch}\n"
        f"[dim]Topology:[/dim] {topology}",
        border_style="magenta",
        box=box.SIMPLE
    ))

    console.print(f"\n[magenta]→[/magenta] Generating configurations from branch: [bold]{branch}[/bold]")
    context.run(f"uv run scripts/get_configs.py --branch {branch}", pty=True)

    topology_file = f"generated-configs/clab/{topology}.clab.yml"
    console.print(f"\n[magenta]→[/magenta] Deploying containerlab topology: [bold]{topology_file}[/bold]")
    context.run(f"sudo -E containerlab deploy -t {topology_file}")

    console.print(f"\n[green]✓[/green] Containerlab topology '[bold green]{topology}[/bold green]' deployed successfully")
    console.print()


@task
def destroy(context: Context) -> None:
    """Destroy all containers."""
    console.print()
    console.print(Panel(
        "[red]Destroying all containers and volumes[/red]",
        border_style="red",
        box=box.SIMPLE
    ))
    context.run(f"{COMPOSE_COMMAND} down -v")
    console.print("[green]✓[/green] All containers and volumes destroyed")


@task
def stop(context: Context) -> None:
    """Stop all containers."""
    console.print()
    console.print(Panel(
        "[yellow]Stopping all containers[/yellow]",
        border_style="yellow",
        box=box.SIMPLE
    ))
    context.run(f"{COMPOSE_COMMAND} down")
    console.print("[green]✓[/green] All containers stopped")


@task
def restart(context: Context, component: str = "") -> None:
    """Restart containers."""
    if component:
        console.print()
        console.print(Panel(
            f"[yellow]Restarting component:[/yellow] [bold]{component}[/bold]",
            border_style="yellow",
            box=box.SIMPLE
        ))
        context.run(f"{COMPOSE_COMMAND} restart {component}")
        console.print(f"[green]✓[/green] Component '{component}' restarted")
        return

    console.print()
    console.print(Panel(
        "[yellow]Restarting all containers[/yellow]",
        border_style="yellow",
        box=box.SIMPLE
    ))
    context.run(f"{COMPOSE_COMMAND} restart")
    console.print("[green]✓[/green] All containers restarted")


@task
def run_tests(context: Context) -> None:
    """Run all tests."""
    console.print()
    console.print(Panel(
        "[bold cyan]Running Tests[/bold cyan]",
        border_style="cyan",
        box=box.SIMPLE
    ))
    context.run("pytest -vv tests")
    console.print("[green]✓[/green] Tests completed")


@task
def validate(context: Context) -> None:
    """Run all code quality tests."""
    console.print()
    console.print(Panel(
        "[bold cyan]Running Code Validation[/bold cyan]\n"
        "[dim]Ruff → Mypy → Pytest[/dim]",
        border_style="cyan",
        box=box.SIMPLE
    ))

    console.print("\n[cyan]→[/cyan] Running Ruff checks...")
    context.run("ruff check . --fix")

    console.print("\n[cyan]→[/cyan] Running Mypy type checks...")
    context.run("mypy .")

    console.print("\n[cyan]→[/cyan] Running Pytest...")
    context.run("pytest -vv tests")

    console.print("\n[green]✓[/green] All validation checks completed!")
    console.print()


@task
def format(context: Context) -> None:
    """Run RUFF to format all Python files."""
    console.print()
    console.print(Panel(
        "[bold magenta]Formatting Python Code[/bold magenta]\n"
        "[dim]Ruff Format → Ruff Fix[/dim]",
        border_style="magenta",
        box=box.SIMPLE
    ))

    exec_cmds = ["ruff format .", "ruff check . --fix"]
    with context.cd(MAIN_DIRECTORY_PATH):
        for cmd in exec_cmds:
            context.run(cmd)

    console.print("[green]✓[/green] Code formatting completed")
    console.print()


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
    console.print()
    console.print(Panel(
        "[bold yellow]Running All Linters[/bold yellow]\n"
        "[dim]YAML → Ruff → Mypy[/dim]",
        border_style="yellow",
        box=box.SIMPLE
    ))

    console.print("\n[yellow]→[/yellow] Running yamllint...")
    lint_yaml(context)

    console.print("\n[yellow]→[/yellow] Running ruff...")
    lint_ruff(context)

    console.print("\n[yellow]→[/yellow] Running mypy...")
    lint_mypy(context)

    console.print("\n[green]✓[/green] All linters completed!")
    console.print()


@task(name="docs")
def docs_build(context: Context) -> None:
    """Build documentation website."""
    console.print()
    console.print(Panel(
        "[bold blue]Building Documentation Website[/bold blue]\n"
        f"[dim]Directory:[/dim] {DOCUMENTATION_DIRECTORY}",
        border_style="blue",
        box=box.SIMPLE
    ))

    exec_cmd = "npm run build"

    with context.cd(DOCUMENTATION_DIRECTORY):
        output = context.run(exec_cmd)

    if output and output.exited != 0:
        console.print("[red]✗[/red] Documentation build failed")
        sys.exit(-1)

    console.print("[green]✓[/green] Documentation built successfully")
    console.print()
