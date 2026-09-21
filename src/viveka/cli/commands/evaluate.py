"""
Development CLI command: viveka evaluate

Runs reproduction testing for a Phase 6 World against an approved Phase 5 Property.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from viveka.evaluation.models import ReproductionPolicy
from viveka.evaluation.reproduction import execute_reproduction
from viveka.properties.store import PropertyStore
from viveka.reporting.console import console
from viveka.worlds.store import WorldStore


def evaluate_command(
    property_id: Annotated[
        str,
        typer.Argument(help="Target Property ID (VPROP-...) or stable key."),
    ],
    world_id: Annotated[
        str,
        typer.Argument(help="Target World ID (VWORLD-...) or filename."),
    ],
    path: Annotated[
        Path,
        typer.Option(
            "--path", help="Path to project directory.", exists=True, file_okay=False, dir_okay=True
        ),
    ] = Path("."),
    runs: Annotated[
        int,
        typer.Option("--runs", "-r", help="Total trial runs to execute."),
    ] = 5,
    minimum_violations: Annotated[
        int,
        typer.Option(
            "--minimum-violations",
            "-m",
            help="Minimum violations required for reproduction criterion.",
        ),
    ] = 3,
    seed: Annotated[
        int,
        typer.Option("--seed", "-s", help="Master seed for reproduction derivation."),
    ] = 12345,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output machine-readable ReproductionResult JSON envelope."),
    ] = False,
) -> None:
    """Evaluate an approved property oracle against a world under a ReproductionPolicy."""
    project_root = (path or Path.cwd()).resolve()

    prop_store = PropertyStore(project_root)
    prop = prop_store.get(property_id) or prop_store.load_catalog().by_stable_key(property_id)

    if not prop:
        if json_output:
            print(json.dumps({"error": f"Property not found: {property_id}"}))
        else:
            console.print(f"[error]Property not found:[/] {property_id}")
        raise typer.Exit(code=1)

    world_store = WorldStore(project_root)
    world = world_store.load(world_id)

    if not world:
        for w in world_store.load_all():
            if w.id == world_id or w.id.startswith(world_id):
                world = w
                break

    if not world:
        if json_output:
            print(json.dumps({"error": f"World not found: {world_id}"}))
        else:
            console.print(f"[error]World not found:[/] {world_id}")
        raise typer.Exit(code=1)

    from viveka.evaluation.store import EvaluationStore

    policy = ReproductionPolicy(runs=runs, minimum_violations=minimum_violations)
    eval_store = EvaluationStore(project_root)

    result = execute_reproduction(
        property=prop,
        world=world,
        policy=policy,
        master_seed=seed,
        evaluation_store=eval_store,
    )

    if json_output:
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        raise typer.Exit(code=0)

    console.print(f"\n[bold]Reproduction Testing Results ({result.property_id}):[/]\n")
    console.print(f"  {'Property':<18} [brand]{prop.name}[/]")
    console.print(f"  {'Stable Key':<18} [muted]{prop.stable_key}[/]")
    console.print(f"  {'Revision':<18} {prop.revision}")
    console.print(f"  {'World ID':<18} {world.id}")
    console.print(f"  {'Master Seed':<18} {seed}")
    console.print()

    console.print(
        f"  [bold]Raw Counts:[/] {result.violations_count} / {result.total_runs} runs violated the property"
    )

    if result.criterion_met:
        console.print("  [success]REPRODUCTION CRITERION MET[/]")
    else:
        console.print("  [warn]REPRODUCTION CRITERION NOT MET[/]")

    console.print()

    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("Run #", width=6)
    table.add_column("Seed", width=12)
    table.add_column("Execution ID", style="bold")
    table.add_column("Trace ID", style="muted")
    table.add_column("Verdict", style="brand")

    for run in result.runs_detail:
        v_style = (
            "[error]VIOLATION[/]"
            if run.verdict == "violation"
            else f"[muted]{run.verdict.value}[/]"
        )
        table.add_row(
            str(run.run_index + 1),
            str(run.derived_seed),
            run.execution_id,
            run.trace_id,
            v_style,
        )

    console.print(table)
    console.print()
