"""
CLI command group: viveka regression

Manages durable behavioral regression artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from viveka.core.ids import short_display
from viveka.diagnosis.models import TargetMetadata
from viveka.diagnosis.store import DiagnosisStore
from viveka.evaluation.store import EvaluationStore
from viveka.properties.store import PropertyStore
from viveka.reduction.store import ReductionStore
from viveka.regression.engine import RegressionEngine
from viveka.regression.store import RegressionStore
from viveka.reporting.console import console
from viveka.worlds.store import WorldStore

regression_app = typer.Typer(
    name="regression",
    help="Manage durable behavioral regression artifacts.",
    no_args_is_help=True,
)


@regression_app.command("create")
def create_regression_command(
    reduction_id: Annotated[
        str,
        typer.Argument(help="Reduction ID (VRED-...) to turn into a regression."),
    ],
    path: Annotated[
        Path,
        typer.Option(
            "--path", help="Path to project directory.", exists=True, file_okay=False, dir_okay=True
        ),
    ] = Path("."),
    model: Annotated[
        str | None,
        typer.Option("--model", help="Target model name for metadata recording."),
    ] = None,
    provider: Annotated[
        str | None,
        typer.Option("--provider", help="Target provider name for metadata recording."),
    ] = None,
    git_commit: Annotated[
        str | None,
        typer.Option("--git-commit", help="Target git commit SHA for metadata recording."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output machine-readable BehavioralRegression JSON envelope."),
    ] = False,
) -> None:
    """Create a durable BehavioralRegression artifact from a ReductionResult."""
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
            f"but ReductionResult recorded revision {reduction.property_revision}. "
            "Cannot create regression from mismatched property revision."
        )
        if json_output:
            print(json.dumps({"error": err_msg}))
        else:
            console.print(f"[error]{err_msg}[/]")
        raise typer.Exit(code=1)

    world_store = WorldStore(project_root)
    diag_store = DiagnosisStore(project_root)
    eval_store = EvaluationStore(project_root)
    reg_store = RegressionStore(project_root)

    engine = RegressionEngine(
        property_store=prop_store,
        world_store=world_store,
        reduction_store=red_store,
        diagnosis_store=diag_store,
        regression_store=reg_store,
        evaluation_store=eval_store,
    )

    metadata = None
    if model or provider or git_commit:
        metadata = TargetMetadata(
            model=model,
            provider=provider,
            git_commit=git_commit,
        )

    try:
        regression = engine.create(
            reduction_result=reduction,
            property_obj=prop,
            target_metadata=metadata,
        )
    except ValueError as e:
        if json_output:
            print(json.dumps({"error": str(e)}))
        else:
            console.print(f"[error]Regression Creation Error:[/] {e}")
        raise typer.Exit(code=1) from e

    if json_output:
        print(json.dumps(regression.model_dump(mode="json"), indent=2))
        raise typer.Exit(code=0)

    console.print(f"\n[bold]Behavioral Regression Created ({regression.regression_id}):[/]\n")
    console.print(f"  {'Regression ID':<22} [brand]{regression.regression_id}[/]")
    console.print(f"  {'Fingerprint':<22} [muted]{regression.fingerprint[:16]}...[/]")
    console.print(f"  {'Property':<22} [brand]{prop.name}[/]")
    console.print(f"  {'Property Stable Key':<22} [muted]{regression.property_stable_key}[/]")
    console.print(f"  {'Property Revision':<22} {regression.property_revision}")
    console.print(f"  {'Reduction ID':<22} {regression.reduction_id}")
    console.print(f"  {'Final World ID':<22} {regression.final_world_snapshot.id}")
    console.print(f"  {'Diagnosis ID':<22} {regression.diag_id or '[muted]None[/]'}")
    console.print(
        f"  {'Historical Violations':<22} {regression.historical_reproduction.violations_count} / {regression.historical_reproduction.total_runs}"
    )
    console.print()

    # Privacy notice
    console.print(
        "  [warn]Privacy notice: Stored regression artifacts may contain retrieved content,[/]\n"
        "  [warn]tool inputs/results, PII, or other target data. Review before sharing or committing.[/]\n"
    )


@regression_app.command("list")
def list_regressions_command(
    path: Annotated[
        Path,
        typer.Option(
            "--path", help="Path to project directory.", exists=True, file_okay=False, dir_okay=True
        ),
    ] = Path("."),
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output machine-readable JSON envelope."),
    ] = False,
) -> None:
    """List all stored BehavioralRegression artifacts."""
    project_root = (path or Path.cwd()).resolve()
    reg_store = RegressionStore(project_root)
    regressions = reg_store.load_all()

    if json_output:
        out = {
            "total": len(regressions),
            "regressions": [r.model_dump(mode="json") for r in regressions],
        }
        print(json.dumps(out, indent=2))
        raise typer.Exit(code=0)

    if not regressions:
        console.print(
            "[muted]No stored regressions found. Run `viveka regression create <REDUCTION_ID>` to create one.[/]"
        )
        return

    console.print(f"\n[bold]Stored Behavioral Regressions ({len(regressions)}):[/]\n")
    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("Regression ID", style="bold")
    table.add_column("Property Stable Key", style="muted")
    table.add_column("Rev", width=4)
    table.add_column("Historical K/N", width=14)
    table.add_column("Created At", style="dim")

    for r in regressions:
        hist_kn = (
            f"{r.historical_reproduction.violations_count} / {r.historical_reproduction.total_runs}"
        )
        table.add_row(
            short_display(r.regression_id),
            r.property_stable_key,
            str(r.property_revision),
            hist_kn,
            r.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)
    console.print()


@regression_app.command("show")
def show_regression_command(
    regression_id: Annotated[
        str,
        typer.Argument(help="Regression ID (VREG-...) or short display ID."),
    ],
    path: Annotated[
        Path,
        typer.Option(
            "--path", help="Path to project directory.", exists=True, file_okay=False, dir_okay=True
        ),
    ] = Path("."),
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output machine-readable JSON envelope."),
    ] = False,
) -> None:
    """Show details of a stored BehavioralRegression artifact."""
    project_root = (path or Path.cwd()).resolve()
    reg_store = RegressionStore(project_root)

    regression = reg_store.load(regression_id)
    if not regression:
        for r in reg_store.load_all():
            if (
                r.regression_id == regression_id
                or r.regression_id.startswith(regression_id)
                or short_display(r.regression_id) == regression_id
            ):
                regression = r
                break

    if not regression:
        if json_output:
            print(json.dumps({"error": f"Regression not found: {regression_id}"}))
        else:
            console.print(f"[error]Regression not found:[/] {regression_id}")
        raise typer.Exit(code=1)

    if json_output:
        print(json.dumps(regression.model_dump(mode="json"), indent=2))
        raise typer.Exit(code=0)

    console.print(f"\n[bold]Behavioral Regression Details ({regression.regression_id}):[/]\n")
    console.print(f"  {'Regression ID':<24} [brand]{regression.regression_id}[/]")
    console.print(f"  {'Fingerprint':<24} [muted]{regression.fingerprint}[/]")
    console.print(f"  {'Property Stable Key':<24} [muted]{regression.property_stable_key}[/]")
    console.print(f"  {'Property Revision':<24} {regression.property_revision}")
    console.print(f"  {'Reduction ID':<24} {regression.reduction_id}")
    console.print(f"  {'Diagnosis ID':<24} {regression.diag_id or '[muted]None[/]'}")
    console.print(f"  {'Final World ID':<24} {regression.final_world_snapshot.id}")
    console.print(f"  {'Original World ID':<24} {regression.original_world_id}")
    console.print(f"  {'Master Seed':<24} {regression.master_seed}")
    console.print(f"  {'Seed Namespace':<24} {regression.seed_namespace}")
    console.print(
        f"  {'Reproduction Policy':<24} {regression.reproduction_policy.runs} runs, minimum {regression.reproduction_policy.minimum_violations} violations"
    )
    console.print(
        f"  {'Historical Violations':<24} {regression.historical_reproduction.violations_count} / {regression.historical_reproduction.total_runs}"
    )
    console.print(f"  {'VIVEKA Version':<24} {regression.viveka_version}")
    console.print(f"  {'Created At':<24} {regression.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    console.print()

    if regression.diagnosis_snapshot:
        diag = regression.diagnosis_snapshot
        console.print("  [heading]Diagnosis Snapshot[/]")
        console.print(f"    Expected: {diag.expected_behavior}")
        console.print(f"    Observed: {diag.observed_behavior}")
        console.print()

    if regression.representative_evidence:
        console.print("  [heading]Representative Evidence Snapshots[/]")
        for rep in regression.representative_evidence:
            console.print(
                f"    • Verdict: [bold]{rep.verdict.value}[/] | Execution: {rep.execution_id} | Trace: {rep.trace_id}"
            )
        console.print()
