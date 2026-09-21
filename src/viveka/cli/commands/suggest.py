"""
CLI command group: viveka suggest

Provides optional advisory model suggestions for properties and worlds.
Requires a configured reasoning provider (e.g. Ollama).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table

from viveka.capabilities import (
    CapabilityAnalysisResult,
    build_capability_graph,
    classify_capabilities,
    infer_trust_boundaries,
)
from viveka.core.config import load_config
from viveka.core.errors import ConfigurationError
from viveka.core.ids import short_display
from viveka.core.paths import project_config_path
from viveka.evaluation.binding import get_demo_capability_binding
from viveka.inspection.analyzer import analyze_python_repository
from viveka.inspection.scanner import scan_repository
from viveka.properties.store import PropertyStore
from viveka.reasoning.advisors.property_advisor import PropertySuggestionAdvisor
from viveka.reasoning.advisors.world_advisor import WorldSuggestionAdvisor
from viveka.reasoning.budget import AdvisoryBudget
from viveka.reasoning.factory import create_provider
from viveka.reporting.console import console
from viveka.worlds.store import WorldStore

suggest_app = typer.Typer(
    name="suggest",
    help="Advisory model suggestions for properties and worlds.",
    no_args_is_help=True,
)


@suggest_app.command("properties")
def suggest_properties_command(
    path: Annotated[
        Path,
        typer.Argument(
            help="Path to project directory.", exists=True, file_okay=False, dir_okay=True
        ),
    ] = Path("."),
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output suggestions in machine-readable JSON format."),
    ] = False,
) -> None:
    """Suggest candidate behavioral properties using advisory model reasoning."""
    project_root = (path or Path.cwd()).resolve()

    cfg_path = project_config_path(project_root)
    if not cfg_path.is_file():
        raise ConfigurationError(
            f"No configuration file found at {cfg_path}.",
            hint="Run `viveka init` to create a project configuration.",
        )
    try:
        cfg = load_config(cfg_path)
        provider = create_provider(cfg)
        if provider is None:
            raise ConfigurationError(
                f"Reasoning is disabled (reasoning.mode: {cfg.reasoning.mode}). "
                "Configure a reasoning provider in .viveka/config.yaml (e.g., mode: local, provider: {type: ollama, model: llama3.2:3b}).",
                hint="Set reasoning.mode to 'local' or configure a provider to use advisory suggestions.",
            )

        # 1. Run static capability analysis
        scan_summary = scan_repository(project_root)
        static_result = analyze_python_repository(project_root, scan_summary)
        capabilities, stats = classify_capabilities(static_result)
        boundaries = infer_trust_boundaries(capabilities)
        graph = build_capability_graph(static_result, capabilities)
        cap_analysis = CapabilityAnalysisResult(
            capabilities=capabilities,
            trust_boundaries=boundaries,
            graph=graph,
            statistics=stats,
        )

        # 2. Load existing properties
        prop_store = PropertyStore(project_root)
        existing_catalog = prop_store.load_catalog()

        # 3. Run suggestion advisor
        budget = AdvisoryBudget(max_calls=cfg.reasoning.max_advisory_calls)
        advisor = PropertySuggestionAdvisor(provider, budget=budget)
        result = advisor.suggest(cap_analysis, existing_catalog=existing_catalog)

        # 4. Save suggestions to PropertyStore as CANDIDATE
        for p in result.suggested_candidates:
            prop_store.save(p)
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

    if json_output:
        out_dict = {
            "suggested_count": len(result.suggested_candidates),
            "rejected_count": len(result.rejected_proposals),
            "candidates": [p.model_dump(mode="json") for p in result.suggested_candidates],
            "rejected": result.rejected_proposals,
        }
        print(json.dumps(out_dict, indent=2))
        return

    console.print("\n[bold]VIVEKA Advisory Property Suggestions[/]\n")
    console.print(f"  {'Provider':<20} [brand]{provider.provider_kind} ({provider.model_name})[/]")
    console.print(f"  {'Suggested (New)':<20} [ok]{len(result.suggested_candidates)}[/]")
    console.print(f"  {'Rejected / Dupes':<20} {len(result.rejected_proposals)}")
    console.print()

    if result.suggested_candidates:
        table = Table(show_header=True, header_style="bold cyan", box=None)
        table.add_column("Property ID", style="bold")
        table.add_column("Name", style="brand")
        table.add_column("Status", style="muted")
        table.add_column("Description")

        for p in result.suggested_candidates:
            table.add_row(
                short_display(p.id),
                p.name,
                f"[{p.status.value}]",
                p.description,
            )
        console.print(table)
        console.print()
        console.print(
            "  [muted]All suggestions entered as CANDIDATE. "
            "Run `viveka properties approve <ID>` to approve for verification.[/]\n"
        )

    if result.rejected_proposals:
        console.print("  [muted]Rejected / duplicate suggestions:[/]")
        for rej in result.rejected_proposals:
            console.print(
                f"    - {rej.get('proposal_name', 'Unnamed')}: [muted]{rej.get('reason')}[/]"
            )
        console.print()


@suggest_app.command("worlds")
def suggest_worlds_command(
    path: Annotated[
        Path,
        typer.Argument(
            help="Path to project directory.", exists=True, file_okay=False, dir_okay=True
        ),
    ] = Path("."),
    property_filter: Annotated[
        str,
        typer.Option("--property", "-p", help="Target approved Property ID or stable key."),
    ] = ...,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output suggestions in machine-readable JSON format."),
    ] = False,
) -> None:
    """Suggest adversarial Worlds for an approved Property using advisory model reasoning."""
    project_root = (path or Path.cwd()).resolve()

    cfg_path = project_config_path(project_root)
    if not cfg_path.is_file():
        raise ConfigurationError(
            f"No configuration file found at {cfg_path}.",
            hint="Run `viveka init` to create a project configuration.",
        )
    try:
        cfg = load_config(cfg_path)
        provider = create_provider(cfg)
        if provider is None:
            raise ConfigurationError(
                f"Reasoning is disabled (reasoning.mode: {cfg.reasoning.mode}). "
                "Configure a reasoning provider in .viveka/config.yaml.",
                hint="Set reasoning.mode to 'local' or configure a provider to use advisory suggestions.",
            )

        prop_store = PropertyStore(project_root)
        prop = prop_store.get(property_filter)
        if prop is None:
            raise ConfigurationError(
                f"Property not found: '{property_filter}'.",
                hint="Run `viveka properties list` to see available properties.",
            )

        world_store = WorldStore(project_root)
        binding = get_demo_capability_binding()

        budget = AdvisoryBudget(max_calls=cfg.reasoning.max_advisory_calls)
        advisor = WorldSuggestionAdvisor(provider, budget=budget)
        result = advisor.suggest(prop, available_tools=binding)

        for w in result.suggested_worlds:
            world_store.save(w)
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

    if json_output:
        out_dict = {
            "property_id": prop.id,
            "suggested_count": len(result.suggested_worlds),
            "rejected_count": len(result.rejected_proposals),
            "worlds": [w.model_dump(mode="json") for w in result.suggested_worlds],
            "rejected": result.rejected_proposals,
        }
        print(json.dumps(out_dict, indent=2))
        return

    console.print("\n[bold]VIVEKA Advisory World Suggestions[/]\n")
    console.print(f"  {'Property':<20} [brand]{prop.name}[/]")
    console.print(f"  {'Provider':<20} [brand]{provider.provider_kind} ({provider.model_name})[/]")
    console.print(f"  {'Suggested Worlds':<20} [ok]{len(result.suggested_worlds)}[/]")
    console.print()

    if result.suggested_worlds:
        for w in result.suggested_worlds:
            console.print(f"  [bold]World {short_display(w.id)}[/] [muted]({w.origin})[/]")
            console.print(f"    Message: {w.input.message}")
            if w.retrieval.documents:
                console.print(f"    Documents: {len(w.retrieval.documents)} doc(s)")
            if w.tools:
                console.print(f"    Tool Overrides: {list(w.tools.keys())}")
            console.print()
