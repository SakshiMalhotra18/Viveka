"""
Flagship CLI command: viveka verify

Runs the end-to-end verification pipeline over approved properties.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from viveka.core.config import load_config
from viveka.core.errors import ConfigurationError
from viveka.core.ids import short_display
from viveka.core.paths import project_config_path
from viveka.diagnosis.store import DiagnosisStore
from viveka.evaluation.binding import get_demo_capability_binding
from viveka.evaluation.models import ReproductionPolicy
from viveka.evaluation.store import EvaluationStore
from viveka.properties.store import PropertyStore
from viveka.reduction.models import ReductionBudget
from viveka.reduction.store import ReductionStore
from viveka.regression.store import RegressionStore
from viveka.reporting.console import console
from viveka.runtime.models import TargetSpec
from viveka.verification.engine import VerificationEngine
from viveka.verification.vocabulary import PropertyVerificationStatus, VerificationOutcome
from viveka.worlds.store import WorldStore


def verify_command(
    path: Annotated[
        Path,
        typer.Argument(
            help="Path to project directory.", exists=True, file_okay=False, dir_okay=True
        ),
    ] = Path("."),
    property_filter: Annotated[
        str | None,
        typer.Option(
            "--property",
            "-p",
            help="Target specific approved Property ID or stable key.",
        ),
    ] = None,
    no_regression: Annotated[
        bool,
        typer.Option(
            "--no-regression",
            help="Execute verification without creating durable BehavioralRegression artifacts.",
        ),
    ] = False,
    runs: Annotated[
        int | None,
        typer.Option("--runs", "-r", help="Reproduction policy trial runs per world."),
    ] = None,
    minimum_violations: Annotated[
        int | None,
        typer.Option(
            "--minimum-violations", "-m", help="Minimum violations for reproduction criterion."
        ),
    ] = None,
    seed: Annotated[
        int,
        typer.Option(
            "--seed", "-s", help="Master seed for stochastic derivation and world generation."
        ),
    ] = 12345,
    max_worlds: Annotated[
        int,
        typer.Option("--max-worlds", help="Maximum adversarial test worlds per property."),
    ] = 3,
    target: Annotated[
        str | None,
        typer.Option("--target", "-t", help="Target import path (e.g. 'module:function')."),
    ] = None,
    enrich: Annotated[
        bool,
        typer.Option(
            "--enrich",
            help="Enable optional advisory reasoning enrichment (e.g. diagnosis narratives).",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output machine-readable VerificationResult JSON envelope."),
    ] = False,
    junit_path: Annotated[
        Path | None,
        typer.Option(
            "--junit",
            help="Write JUnit XML report to the specified file path.",
        ),
    ] = None,
) -> None:
    """Run property-based verification against the target AI agent."""
    project_root = (path or Path.cwd()).resolve()

    cfg = None
    cfg_path = project_config_path(project_root)
    if cfg_path.is_file():
        try:
            cfg = load_config(cfg_path)
        except Exception:
            pass

    prop_store = PropertyStore(project_root)
    world_store = WorldStore(project_root)
    red_store = ReductionStore(project_root)
    diag_store = DiagnosisStore(project_root)
    reg_store = RegressionStore(project_root)
    eval_store = EvaluationStore(project_root)

    engine = VerificationEngine(
        project_root=project_root,
        property_store=prop_store,
        world_store=world_store,
        reduction_store=red_store,
        diagnosis_store=diag_store,
        regression_store=reg_store,
        evaluation_store=eval_store,
        config=cfg,
    )

    explicit_target = None
    explicit_binding = None
    if target:
        explicit_target = TargetSpec(
            adapter_type="python_callable",
            import_path=target,
        )
        if target == "viveka.demo.agent:run_demo_agent":
            explicit_binding = get_demo_capability_binding()

    policy = None
    if runs is not None or minimum_violations is not None:
        eff_runs = runs or 5
        eff_min = minimum_violations or 3
        policy = ReproductionPolicy(runs=eff_runs, minimum_violations=eff_min)

    try:
        result = engine.verify(
            property_filter=property_filter,
            policy=policy,
            budget=ReductionBudget(max_candidates=10, max_trials=50),
            master_seed=seed,
            max_worlds_per_property=max_worlds,
            create_regression=not no_regression,
            target_spec=explicit_target,
            binding=explicit_binding,
            enrich=enrich,
        )
    except ConfigurationError as exc:
        if json_output:
            print(json.dumps({"error": exc.message, "hint": exc.hint}))
        else:
            console.print(f"[error]Configuration Error:[/] {exc.message}")
            if exc.hint:
                console.print(f"[muted]  → {exc.hint}[/]")
        raise typer.Exit(code=2) from None
    except Exception as exc:
        if json_output:
            print(json.dumps({"error": str(exc)}))
        else:
            console.print(f"[error]Operational Error:[/] {exc}")
        raise typer.Exit(code=3) from exc

    # Write JUnit XML report to file if requested (independent of --json)
    if junit_path is not None:
        from viveka.reporting.junit import export_junit_xml

        try:
            export_junit_xml(result, junit_path)
        except Exception as exc:
            import sys

            print(f"Warning: Failed to write JUnit XML report: {exc}", file=sys.stderr)

    if json_output:
        print(json.dumps(result.model_dump(mode="json"), indent=2))
        if result.outcome == VerificationOutcome.NO_REPRODUCED_VIOLATIONS:
            raise typer.Exit(code=0)
        elif result.outcome == VerificationOutcome.REPRODUCED_VIOLATIONS_FOUND:
            raise typer.Exit(code=1)
        elif result.outcome == VerificationOutcome.NO_APPROVED_PROPERTIES:
            raise typer.Exit(code=2)
        else:
            raise typer.Exit(code=3)

    console.print("\n[bold]VIVEKA Verification Summary[/]\n")
    console.print(f"  {'Outcome':<24} [bold]{result.outcome.value}[/]")
    console.print(f"  {'Target Command':<24} [brand]{result.target_command or 'N/A'}[/]")
    console.print(f"  {'Properties Considered':<24} {result.properties_considered}")
    console.print(f"  {'Properties Verified':<24} {result.properties_verified}")
    console.print(f"  {'Worlds Tested':<24} {result.total_worlds_tested}")
    console.print(f"  {'Regressions Created':<24} {result.regressions_created}")
    console.print()

    if result.property_results:
        console.print("  [heading]Property Verification Details[/]")
        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("Property Name", style="bold")
        table.add_column("Stable Key", style="muted")
        table.add_column("Status", width=12)
        table.add_column("Worlds (Violated/Tested)", width=24)
        table.add_column("Regression ID", style="brand")

        for pr in result.property_results:
            if pr.status == PropertyVerificationStatus.NO_REPRODUCED_VIOLATION:
                st = "[ok]NO REPRODUCED VIOLATION[/]"
            elif pr.status == PropertyVerificationStatus.REPRODUCED_VIOLATION:
                st = "[error]REPRODUCED VIOLATION[/]"
            elif pr.status == PropertyVerificationStatus.ERROR:
                st = "[error]ERROR[/]"
            else:
                st = f"[muted]{pr.status.value}[/]"

            reg_str = short_display(pr.regression_id) if pr.regression_id else "-"
            table.add_row(
                pr.property_name,
                pr.property_stable_key,
                st,
                f"{pr.worlds_violated} / {pr.worlds_tested}",
                reg_str,
            )
        console.print(table)
        console.print()

        # Display advisory narratives if present
        for pr in result.property_results:
            if pr.advisory_narrative:
                console.print(f"  [bold cyan]Advisory Diagnosis Narrative ({pr.property_name})[/]")
                console.print(f"  [muted]{pr.advisory_narrative}[/]\n")

    console.print(f"  [muted]{result.summary_message}[/]\n")

    if (
        result.candidate_properties_count > 0
        and result.outcome == VerificationOutcome.NO_APPROVED_PROPERTIES
    ):
        console.print(
            f"  [warn]Notice: {result.candidate_properties_count} candidate properties are pending review.[/]\n"
            "  [warn]Run `viveka properties list` and `viveka properties approve <ID>` to activate verification.[/]\n"
        )

    if result.regressions_created > 0:
        console.print(
            "  [muted]Durable regressions were created. Run `viveka regression list` or `viveka replay <ID>` to inspect.[/]\n"
        )

    # Determine exit code
    if result.outcome == VerificationOutcome.NO_REPRODUCED_VIOLATIONS:
        raise typer.Exit(code=0)
    elif result.outcome == VerificationOutcome.REPRODUCED_VIOLATIONS_FOUND:
        raise typer.Exit(code=1)
    elif result.outcome == VerificationOutcome.NO_APPROVED_PROPERTIES:
        raise typer.Exit(code=2)
    else:
        raise typer.Exit(code=3)
