"""
Development CLI command: viveka reduce

Performs reproducible failure reduction over a failing Phase 6 World against an approved Property.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from viveka.evaluation.models import ReproductionPolicy
from viveka.evaluation.store import EvaluationStore
from viveka.properties.store import PropertyStore
from viveka.reduction.engine import ReductionEngine
from viveka.reduction.models import ReductionBudget
from viveka.reduction.store import ReductionStore
from viveka.reporting.console import console
from viveka.worlds.store import WorldStore


def reduce_command(
    property_id: Annotated[
        str,
        typer.Argument(help="Target Property ID (VPROP-...) or stable key."),
    ],
    world_id: Annotated[
        str,
        typer.Argument(help="Original failing World ID (VWORLD-...) or filename."),
    ],
    path: Annotated[
        Path,
        typer.Option(
            "--path", help="Path to project directory.", exists=True, file_okay=False, dir_okay=True
        ),
    ] = Path("."),
    runs: Annotated[
        int,
        typer.Option("--runs", "-r", help="Total trial runs to execute per candidate."),
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
    max_candidates: Annotated[
        int,
        typer.Option("--max-candidates", help="Maximum candidate worlds to test."),
    ] = 10,
    max_trials: Annotated[
        int,
        typer.Option(
            "--max-trials", help="Maximum total trial runs across baseline + candidate testing."
        ),
    ] = 50,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output machine-readable ReductionResult JSON envelope."),
    ] = False,
) -> None:
    """Greedily reduce a failing World to a simpler Reduced Failure World."""
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

    policy = ReproductionPolicy(runs=runs, minimum_violations=minimum_violations)
    budget = ReductionBudget(max_candidates=max_candidates, max_trials=max_trials)
    reduction_store = ReductionStore(project_root)
    eval_store = EvaluationStore(project_root)

    engine = ReductionEngine(
        world_store=world_store,
        reduction_store=reduction_store,
        evaluation_store=eval_store,
    )

    try:
        result = engine.reduce(
            property_obj=prop,
            world=world,
            policy=policy,
            budget=budget,
            master_seed=seed,
        )
    except ValueError as e:
        if json_output:
            print(json.dumps({"error": str(e)}))
        else:
            console.print(f"[error]Validation Error:[/] {e}")
        raise typer.Exit(code=1) from e

    if json_output:
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        raise typer.Exit(code=0)

    console.print(f"\n[bold]Reproducible Failure Reduction Results ({result.reduction_id}):[/]\n")
    console.print(f"  {'Property':<20} [brand]{prop.name}[/]")
    console.print(f"  {'Original World ID':<20} {result.original_world_id}")
    console.print(
        f"  {'Reduced World ID':<20} {result.reduced_world_id or '[muted]None (No reduction)[/]'}"
    )
    console.print(f"  {'Stop Reason':<20} [bold]{result.stop_reason.value}[/]")
    console.print(
        f"  {'Trial Counts':<20} Baseline: {result.baseline_trials}, Candidates: {result.candidate_trials}, Total: {result.total_trials}"
    )
    console.print()

    console.print(f"  [bold]Summary:[/] {result.summary_message}")
    console.print()

    if result.steps:
        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("#", width=4)
        table.add_column("Candidate", width=10)
        table.add_column("Operator", style="brand")
        table.add_column("Target Item", style="muted")
        table.add_column("Status", width=12)

        for step in result.steps:
            status_str = "[success]ACCEPTED[/]" if step.accepted else "[error]REJECTED[/]"
            table.add_row(
                str(step.step_index),
                step.candidate_id,
                step.operator.value,
                step.target_item_key,
                status_str,
            )

        console.print(table)
        console.print()
