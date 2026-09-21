"""
CLI command group: viveka worlds

Provides subcommands to generate, list, and show test worlds for approved properties.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
import yaml

from viveka.core.config import load_config
from viveka.properties.store import PropertyStore
from viveka.reporting.console import console
from viveka.worlds.generate import WorldGenerator
from viveka.worlds.store import WorldStore

worlds_app = typer.Typer(
    name="worlds",
    help="Generate, list, and inspect test worlds for approved properties.",
    no_args_is_help=True,
)


@worlds_app.command("generate")
def generate_worlds_command(
    path: Annotated[
        Path,
        typer.Argument(
            help="Path to project directory.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = Path("."),
    seed: Annotated[
        int | None,
        typer.Option("--seed", "-s", help="Random seed for deterministic generation."),
    ] = None,
    max_per_property: Annotated[
        int,
        typer.Option(
            "--max-per-property", "-m", help="Maximum worlds to generate per approved property."
        ),
    ] = 10,
    property_id: Annotated[
        str | None,
        typer.Option("--property", "-p", help="Target a specific property ID or stable key."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output machine-readable JSON envelope."),
    ] = False,
) -> None:
    project_root = path.resolve()
    config_path = project_root / ".viveka" / "config.yaml"
    cfg = load_config(config_path) if config_path.is_file() else None
    effective_seed = seed if seed is not None else (cfg.verification.seed if cfg else 12345)

    prop_store = PropertyStore(project_root)
    catalog = prop_store.load_catalog()

    approved_props = catalog.approved
    if property_id:
        target = catalog.by_id(property_id) or catalog.by_stable_key(property_id)
        if target:
            approved_props = [target]
        else:
            if not json_output:
                console.print(f"[error]Property not found:[/] {property_id}")
            raise typer.Exit(code=1)

    if not approved_props:
        if json_output:
            console.print(json.dumps({"status": "no_approved_properties", "worlds_generated": 0}))
        else:
            console.print(
                "[warn]No approved properties found in .viveka/properties/[/]\n"
                "[muted]Run `viveka properties approve <ID>` to approve candidate properties first.[/]"
            )
        raise typer.Exit(code=0)

    generator = WorldGenerator(seed=effective_seed)
    generated = generator.generate_worlds(approved_props, max_worlds_per_property=max_per_property)

    world_store = WorldStore(project_root)
    world_store.save_all(generated)

    if json_output:
        out = {
            "status": "success",
            "seed": effective_seed,
            "approved_properties_targeted": len(approved_props),
            "worlds_generated": len(generated),
            "worlds": [w.model_dump(mode="json") for w in generated],
        }
        print(json.dumps(out, indent=2))
        raise typer.Exit(code=0)
    else:
        console.print(
            f"\n[success]Generated [bold]{len(generated)}[/] world(s)[/] "
            f"for [bold]{len(approved_props)}[/] approved property/properties "
            f"(seed: {effective_seed})."
        )
        console.print(f"[muted]Saved to: {world_store.worlds_dir}[/]\n")

        for w in generated:
            mut_count = len(w.mutations)
            console.print(
                f"  • [bold]{w.id}[/] → Property: [muted]{w.property_stable_key}[/] "
                f"({mut_count} mutation(s))"
            )


@worlds_app.command("list")
def list_worlds_command(
    path: Annotated[
        Path,
        typer.Argument(
            help="Path to project directory.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = Path("."),
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output machine-readable JSON envelope."),
    ] = False,
) -> None:
    """List stored test worlds."""
    project_root = path.resolve()
    world_store = WorldStore(project_root)
    worlds = world_store.load_all()

    if json_output:
        out = {
            "total_worlds": len(worlds),
            "worlds": [w.model_dump(mode="json") for w in worlds],
        }
        print(json.dumps(out, indent=2))
        raise typer.Exit(code=0)
    else:
        if not worlds:
            console.print(
                "[muted]No generated worlds found. Run `viveka worlds generate .` to create worlds.[/]"
            )
            return

        console.print(f"\n[bold]Stored Worlds ({len(worlds)}):[/]\n")
        for w in worlds:
            console.print(
                f"  [bold]{w.id}[/] | Property: [muted]{w.property_stable_key}[/] | "
                f"Mutations: {len(w.mutations)} | Seed: {w.seed}"
            )


@worlds_app.command("show")
def show_world_command(
    world_id: Annotated[str, typer.Argument(help="World ID or filename.")],
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
    """Show details of a stored world definition."""
    project_root = path.resolve()
    world_store = WorldStore(project_root)
    world = world_store.load(world_id)

    if not world:
        if json_output:
            print(json.dumps({"error": f"World not found: {world_id}"}))
        else:
            console.print(f"[error]World not found:[/] {world_id}")
        raise typer.Exit(code=1)

    if json_output:
        print(json.dumps(world.model_dump(mode="json"), indent=2))
        raise typer.Exit(code=0)
    else:
        dumped = world.model_dump(mode="json")
        yaml_text = yaml.safe_dump(dumped, sort_keys=False, allow_unicode=True)
        console.print(f"\n[bold]World {world.id}:[/]\n")
        console.print(yaml_text)
