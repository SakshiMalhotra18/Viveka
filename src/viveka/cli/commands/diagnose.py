"""
CLI command: viveka diagnose

Produces an evidence-grounded deterministic diagnosis of a reduced failure.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from viveka.diagnosis.engine import DiagnosisEngine
from viveka.diagnosis.store import DiagnosisStore
from viveka.evaluation.store import EvaluationStore
from viveka.properties.store import PropertyStore
from viveka.reduction.store import ReductionStore
from viveka.reporting.console import console


def diagnose_command(
    reduction_id: Annotated[
        str,
        typer.Argument(help="Reduction ID (VRED-...) to diagnose."),
    ],
    path: Annotated[
        Path,
        typer.Option(
            "--path", help="Path to project directory.", exists=True, file_okay=False, dir_okay=True
        ),
    ] = Path("."),
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output machine-readable Diagnosis JSON envelope."),
    ] = False,
) -> None:
    """Produce an evidence-based diagnosis of a reproducible failure reduction."""
    project_root = (path or Path.cwd()).resolve()

    red_store = ReductionStore(project_root)
    reduction = red_store.load(reduction_id)
    if not reduction:
        for r in red_store.load_all():
            if r.reduction_id == reduction_id or r.reduction_id.startswith(reduction_id):
                reduction = r
                break

    if not reduction:
        if json_output:
            print(json.dumps({"error": f"Reduction not found: {reduction_id}"}))
        else:
            console.print(f"[error]Reduction not found:[/] {reduction_id}")
        raise typer.Exit(code=1)

    prop_store = PropertyStore(project_root)
    prop = prop_store.get(reduction.property_id) or prop_store.load_catalog().by_stable_key(
        reduction.property_stable_key
    )

    if not prop:
        if json_output:
            print(json.dumps({"error": f"Property not found: {reduction.property_id}"}))
        else:
            console.print(f"[error]Property not found:[/] {reduction.property_id}")
        raise typer.Exit(code=1)

    # Property revision mismatch check
    if prop.revision != reduction.property_revision:
        err_msg = (
            f"Property revision mismatch: Property has revision {prop.revision}, "
            f"but ReductionResult recorded revision {reduction.property_revision}."
        )
        if json_output:
            print(json.dumps({"error": err_msg}))
        else:
            console.print(f"[error]{err_msg}[/]")
        raise typer.Exit(code=1)

    eval_store = EvaluationStore(project_root)
    diag_store = DiagnosisStore(project_root)
    engine = DiagnosisEngine()

    try:
        diagnosis = engine.diagnose(
            reduction_result=reduction,
            property_obj=prop,
            evaluation_store=eval_store,
        )
        diag_store.save(diagnosis)
    except ValueError as e:
        if json_output:
            print(json.dumps({"error": str(e)}))
        else:
            console.print(f"[error]Diagnosis Error:[/] {e}")
        raise typer.Exit(code=1) from e

    if json_output:
        print(json.dumps(diagnosis.model_dump(mode="json"), indent=2))
        raise typer.Exit(code=0)

    console.print(f"\n[bold]Behavioral Failure Diagnosis ({diagnosis.diag_id}):[/]\n")
    console.print(f"  {'Diagnosis Method':<22} [muted]{diagnosis.diagnosis_method}[/]")
    console.print(f"  {'Property':<22} [brand]{prop.name}[/]")
    console.print(f"  {'Reduction ID':<22} {diagnosis.reduction_id}")
    console.print(f"  {'World ID':<22} {diagnosis.world_id}")
    console.print(f"  {'Reproduction Summary':<22} {diagnosis.reproduction_summary}")
    console.print()

    console.print("  [bold]Expected Behavior:[/]")
    console.print(f"    {diagnosis.expected_behavior}")
    console.print()

    console.print("  [bold]Observed Behavior:[/]")
    console.print(f"    {diagnosis.observed_behavior}")
    console.print()

    if diagnosis.earliest_relevant_event:
        ere = diagnosis.earliest_relevant_event
        console.print(
            f"  [bold]Earliest Relevant Event:[/] #{ere.sequence} [{ere.event_type.value}] {ere.description}"
        )
        console.print()

    if diagnosis.evidence:
        console.print("  [heading]Observed Evidence Sequence[/]")
        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("Seq #", width=6)
        table.add_column("Type", width=14)
        table.add_column("Event ID", style="muted")
        table.add_column("Description", style="white")

        for ev in diagnosis.evidence:
            table.add_row(
                str(ev.sequence),
                ev.event_type.value,
                ev.event_id,
                ev.description,
            )
        console.print(table)
        console.print()

    if diagnosis.contributing_factors:
        console.print("  [heading]Likely Contributing Factors[/]")
        for factor in diagnosis.contributing_factors:
            console.print(f"  • [bold]{factor.label}[/]")
            console.print(f"    [muted]{factor.description}[/]")
        console.print()

    if diagnosis.limitations:
        console.print("  [heading]Limitations & Disclaimers[/]")
        for lim in diagnosis.limitations:
            console.print(f"  [muted]• {lim}[/]")
        console.print()
