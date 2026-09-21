"""
CLI command: viveka replay

Replays a stored BehavioralRegression artifact using the stored stochastic schedule.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from viveka.core.config import load_config
from viveka.core.ids import short_display
from viveka.core.paths import project_config_path
from viveka.evaluation.binding import get_demo_capability_binding
from viveka.properties.store import PropertyStore
from viveka.regression.replay import ReplayEngine
from viveka.regression.store import RegressionStore
from viveka.reporting.console import console
from viveka.runtime.models import TargetSpec


def replay_command(
    regression_id: Annotated[
        str,
        typer.Argument(help="Regression ID (VREG-...) or short display ID to replay."),
    ],
    path: Annotated[
        Path,
        typer.Option(
            "--path", help="Path to project directory.", exists=True, file_okay=False, dir_okay=True
        ),
    ] = Path("."),
    target: Annotated[
        str | None,
        typer.Option("--target", "-t", help="Target import path (e.g. 'module:function')."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output machine-readable ReplayReport JSON envelope."),
    ] = False,
) -> None:
    """Replay a stored BehavioralRegression against the target agent."""
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
        raise typer.Exit(code=2)

    prop_store = PropertyStore(project_root)
    cfg = None
    cfg_path = project_config_path(project_root)
    if cfg_path.is_file():
        try:
            cfg = load_config(cfg_path)
        except Exception:
            pass

    engine = ReplayEngine(
        project_root=project_root,
        property_store=prop_store,
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

    try:
        report = engine.replay(
            regression=regression,
            target_spec=explicit_target,
            binding=explicit_binding,
        )
    except Exception as e:
        if json_output:
            print(json.dumps({"error": str(e)}))
        else:
            console.print(f"[error]Replay Error:[/] {e}")
        raise typer.Exit(code=3) from e

    if json_output:
        print(json.dumps(report.model_dump(mode="json"), indent=2))
        raise typer.Exit(code=1 if report.current_criterion_met else 0)

    console.print(f"\n[bold]Behavioral Regression Replay Report ({report.regression_id}):[/]\n")
    console.print(f"  {'Property Stable Key':<24} [muted]{report.property_stable_key}[/]")
    console.print(f"  {'Property Revision':<24} {report.property_revision}")
    console.print()

    console.print(
        f"  {'Historical':<14} {report.historical_violations} / {report.historical_runs} violations "
        f"({'MET' if report.historical_criterion_met else 'NOT MET'})"
    )
    console.print(
        f"  {'Current':<14} {report.current_violations} / {report.current_runs} violations "
        f"({'MET' if report.current_criterion_met else 'NOT MET'})"
    )
    status_style = "[error]MET[/]" if report.current_criterion_met else "[success]NOT MET[/]"
    console.print(f"  Current reproduction criterion: {status_style}")
    console.print()

    for obs in report.observations:
        console.print(f"  [muted]• {obs}[/]")
    console.print()

    # Exit codes: 0 = criterion NOT met, 1 = criterion MET
    raise typer.Exit(code=1 if report.current_criterion_met else 0)
