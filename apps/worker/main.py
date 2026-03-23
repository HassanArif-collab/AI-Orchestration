#!/usr/bin/env python3
"""CLI for managing the YouTube pipeline.

Commands:
    start       - Start a new pipeline run
    approve     - Approve a human gate and continue
    status      - Show current pipeline status
    list-runs   - List all pipeline runs
"""

import asyncio
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from packages.pipeline.runner import PipelineRunner
from packages.pipeline.state import RunStore
from packages.pipeline.stages import Stage, is_human_gate

app = typer.Typer(name="pipeline", help="YouTube pipeline manager")
console = Console()


async def start_pipeline() -> str:
    """Start a new pipeline run and execute to first human gate.

    Returns:
        Run ID of the new pipeline run
    """
    runner = PipelineRunner()
    run = await runner.create_run()

    # Execute trend analysis first
    from packages.pipeline.handlers import handle_trend_analysis

    output = await runner.execute_stage(run, Stage.TREND_ANALYSIS)

    # Get video ideas
    ideas = output if output else run.get_output(Stage.TREND_ANALYSIS)

    console.print("\n[bold green]Pipeline started![/bold green]")
    console.print(f"Run ID: {run.run_id}")
    console.print("\n[bold]Video Ideas:[/bold]")

    if ideas:
        for i, idea in enumerate(ideas):
            console.print(f"\n  [{i}] {idea.get('title', 'Untitled')}")
            console.print(f"      Angle: {idea.get('angle', 'N/A')}")
            console.print(f"      Curiosity gap: {idea.get('curiosity_gap', 'N/A')}")
            console.print(f"      Viral score: {idea.get('viral_score', 'N/A')}")

    console.print(f"\n[yellow]Pipeline paused at HUMAN_TOPIC_APPROVAL[/yellow]")
    console.print(f"Use: pipeline approve {run.run_id} --selection <index>")

    return run.run_id


async def approve_and_continue(run_id: str, selection: int = 0) -> None:
    """Approve a human gate and continue the pipeline.

    Args:
        run_id: The run ID to approve
        selection: Index of the selection (for topic approval)
    """
    store = RunStore()
    run = store.load(run_id)

    if not run:
        console.print(f"[red]Error: Run {run_id} not found[/red]")
        raise typer.Exit(code=1)

    runner = PipelineRunner(store)

    # Determine which gate we're at
    current_stage = run.current_stage

    if not is_human_gate(current_stage):
        console.print(f"[red]Error: Run {run_id} is not at a human gate[/red]")
        raise typer.Exit(code=1)

    # Get the output to determine selection
    if current_stage == Stage.HUMAN_TOPIC_APPROVAL:
        ideas = run.get_output(Stage.TREND_ANALYSIS) or []
        if selection < len(ideas):
            chosen = ideas[selection]
            console.print(f"\n[bold]Selected idea:[/bold] {chosen.get('title', 'Untitled')}")
            await runner.approve_gate(run, current_stage, approved=True, selection=chosen)
        else:
            console.print(f"[red]Error: Invalid selection {selection}[/red]")
            raise typer.Exit(code=1)
    else:
        await runner.approve_gate(run, current_stage, approved=True)

    # Continue until next gate
    gate = await runner.run_until_gate(run)

    if gate:
        console.print(f"\n[yellow]Pipeline paused at {gate.value}[/yellow]")
    else:
        console.print(f"\n[bold green]Pipeline completed![/bold green]")

    # Print current status
    print_status(run)


async def show_status(run_id: str) -> None:
    """Show the current status of a pipeline run.

    Args:
        run_id: The run ID to show
    """
    store = RunStore()
    run = store.load(run_id)

    if not run:
        console.print(f"[red]Error: Run {run_id} not found[/red]")
        raise typer.Exit(code=1)

    print_status(run)


def print_status(run) -> None:
    """Print status of a pipeline run.

    Args:
        run: PipelineRun instance
    """
    console.print(f"\n[bold]Pipeline Status:[/bold]")
    console.print(f"Run ID: {run.run_id}")
    console.print(f"Status: {run.status}")
    console.print(f"Current Stage: {run.current_stage.value}")

    table = Table(title="Stage Status")
    table.add_column("Stage", style="cyan")
    table.add_column("Status", style="green")

    for stage in Stage:
        status = run.stage_status.get(stage.value, "pending")
        style = (
            "green" if status == "complete"
            else "yellow" if status == "running" or status == "waiting_human"
            else "red" if status == "error"
            else "dim"
        )
        table.add_row(stage.value, status, style=style)

    console.print(table)


async def list_all_runs() -> None:
    """List all pipeline runs."""
    store = RunStore()
    runs = store.list_runs(limit=20)

    if not runs:
        console.print("[yellow]No pipeline runs found[/yellow]")
        return

    table = Table(title="Pipeline Runs")
    table.add_column("Run ID", style="cyan", no_wrap=True)
    table.add_column("Current Stage", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Updated At", style="dim")

    for run in runs:
        table.add_row(
            run["run_id"][:8] + "...",
            run["current_stage"],
            run["status"],
            run["updated_at"],
        )

    console.print(table)


@app.command()
def start():
    """Start a new pipeline run. Executes stages until a human gate."""
    asyncio.run(start_pipeline())


@app.command()
def approve(
    run_id: str = typer.Argument(..., help="The run ID to approve"),
    selection: int = typer.Option(0, help="Selection index for topic approval"),
):
    """Approve a human gate and continue the pipeline."""
    asyncio.run(approve_and_continue(run_id, selection))


@app.command()
def status(
    run_id: str = typer.Argument(..., help="The run ID to show status for"),
):
    """Show the current state of a pipeline run."""
    asyncio.run(show_status(run_id))


@app.command()
def list_runs():
    """List all pipeline runs."""
    asyncio.run(list_all_runs())


if __name__ == "__main__":
    app()
