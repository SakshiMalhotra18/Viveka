"""
``viveka properties`` — propose, inspect, approve, and manage behavioral properties.

Phase 5 implementation:
  - ``viveka properties list``: List candidate and approved properties.
  - ``viveka properties suggest``: Infer candidate properties from target capabilities.
  - ``viveka properties show ID``: Inspect detailed invariant definition and typed oracle.
  - ``viveka properties approve ID``: Approve candidate property as active verification baseline.
  - ``viveka properties reject ID``: Reject candidate property.
"""

from __future__ import annotations

import json
import sys
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
from viveka.inspection.analyzer import analyze_python_repository
from viveka.inspection.scanner import scan_repository
from viveka.properties.engine import infer_candidate_properties
from viveka.properties.store import PropertyNotFoundError, PropertyStore
from viveka.properties.vocabulary import PropertyStatus
from viveka.reporting.console import BRAND_HEADER, OK, console

properties_app = typer.Typer(
    name="properties",
    help="Author, suggest, and manage behavioral properties.",
    no_args_is_help=True,
)


def _status_style(status: PropertyStatus) -> str:
    if status == PropertyStatus.APPROVED:
        return "[ok]approved[/]"
    if status == PropertyStatus.CANDIDATE:
        return "[warn]candidate[/]"
    if status == PropertyStatus.REJECTED:
        return "[error]rejected[/]"
    if status == PropertyStatus.DISABLED:
        return "[muted]disabled[/]"
    return str(status.value)


@properties_app.command("list")
def list_properties(
    path: Annotated[
        Path | None,
        typer.Argument(
            help="Target repository root path (defaults to current directory).",
            file_okay=False,
            exists=False,
        ),
    ] = None,
    status: Annotated[
        str,
        typer.Option(
            "--status",
            "-s",
            help="Filter by status: 'candidate', 'approved', 'rejected', or 'all'.",
        ),
    ] = "all",
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Output properties catalog as machine-readable JSON.",
        ),
    ] = False,
) -> None:
    """List properties for the project."""
    target_root = (path or Path.cwd()).resolve()
    store = PropertyStore(target_root)
    catalog = store.load_catalog()

    target_status = status.lower()
    if target_status != "all":
        props = [p for p in catalog.properties if p.status.value == target_status]
    else:
        props = catalog.properties

    if json_output:
        data = {
            "schema_version": 1,
            "total": len(props),
            "properties": [p.model_dump(mode="json") for p in props],
        }
        print(json.dumps(data, indent=2))
        raise typer.Exit(code=0)

    console.print(BRAND_HEADER)
    console.print()
    console.print(f"[heading]Repository[/]\n{target_root}")
    console.print()

    if not props:
        console.print("[info]No properties found.[/]")
        console.print(
            "Run [brand]viveka properties suggest[/] to discover candidate properties "
            "from the codebase."
        )
        console.print()
        raise typer.Exit(code=0)

    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("ID", style="bold")
    table.add_column("Status", width=12)
    table.add_column("Name", style="brand")
    table.add_column("Invariant Type", style="muted")

    for p in props:
        table.add_row(
            p.id,
            _status_style(p.status),
            p.name,
            p.oracle.evaluator_kind,
        )

    console.print(table)
    console.print()
    console.print(f"Total: {len(props)} property(ies)")
    console.print()


@properties_app.command("suggest")
def suggest_properties(
    path: Annotated[
        Path | None,
        typer.Argument(
            help="Target repository root path (defaults to current directory).",
            file_okay=False,
            exists=False,
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Output suggested properties as JSON.",
        ),
    ] = False,
) -> None:
    """Infer candidate behavioral properties from target capabilities."""
    target_root = (path or Path.cwd()).resolve()

    if not target_root.exists() or not target_root.is_dir():
        if json_output:
            sys.stderr.write(f"Repository not found: {target_root}\n")
            raise typer.Exit(code=2)
        console.print(f"[error]Repository not found:[/] {target_root}")
        raise typer.Exit(code=2)

    # 1. Pipeline: scan -> static analysis -> capabilities & graph
    scan_summary = scan_repository(target_root)
    static_result = analyze_python_repository(target_root, scan_summary)
    capabilities, cap_stats = classify_capabilities(static_result)
    capability_graph = build_capability_graph(static_result, capabilities)
    trust_boundaries = infer_trust_boundaries(capabilities)

    analysis_result = CapabilityAnalysisResult(
        capabilities=capabilities,
        trust_boundaries=trust_boundaries,
        graph=capability_graph,
        statistics=cap_stats,
    )

    # 2. Infer candidate properties via typed upstream contract
    inferred = infer_candidate_properties(analysis_result)

    # 3. Store and merge with existing properties
    store = PropertyStore(target_root)
    new_props, existing_props = store.merge_candidates(inferred)

    if json_output:
        data = {
            "schema_version": 1,
            "suggested_total": len(inferred),
            "new_candidates": [p.model_dump(mode="json") for p in new_props],
            "existing_preserved": [p.model_dump(mode="json") for p in existing_props],
        }
        print(json.dumps(data, indent=2))
        raise typer.Exit(code=0)

    console.print(BRAND_HEADER)
    console.print()
    console.print(f"[heading]Repository[/]\n{target_root}")
    console.print()
    console.print("[info]Inferring candidate properties from capabilities...[/]")
    console.print()

    console.print(f"  {'Capabilities analyzed':<26} {len(capabilities)}")
    console.print(f"  {'Total candidates inferred':<26} {len(inferred)}")
    console.print(f"  {'New candidates added':<26} [ok]{len(new_props)}[/]")
    console.print(f"  {'Existing preserved':<26} [muted]{len(existing_props)}[/]")
    console.print()

    if new_props:
        console.print("[heading]Proposed Candidate Properties[/]")
        console.print()
        for p in new_props:
            console.print(f"  {OK} [heading]{p.name}[/] [muted]({p.id})[/]")
            console.print(f"     [muted]Invariant:[/] {p.oracle.evaluator_kind}")
            console.print(f"     [muted]Rule:[/] {p.description}")
            console.print(f"     [muted]Rationale:[/] {p.rationale}")
            console.print()

        console.print(
            "[info]To approve a property for verification, run:[/]\n"
            f"  [brand]viveka properties approve {new_props[0].id}[/]"
        )
        console.print()
    elif not inferred:
        console.print("[muted]No candidate properties inferred from current capabilities.[/]")
        console.print()
    else:
        console.print(
            "[info]All inferred candidate properties already exist in .viveka/properties/.[/]"
        )
        console.print()


@properties_app.command("show")
def show_property(
    property_id: Annotated[
        str,
        typer.Argument(help="Property ID (e.g. 'VPROP-01...') or property name slug."),
    ],
    path: Annotated[
        Path | None,
        typer.Option(
            "--path",
            "-p",
            help="Target repository root path (defaults to current directory).",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Output property definition as machine-readable JSON.",
        ),
    ] = False,
) -> None:
    """Display detailed definition of a property."""
    target_root = (path or Path.cwd()).resolve()
    store = PropertyStore(target_root)
    prop = store.get(property_id)

    if prop is None:
        if json_output:
            sys.stderr.write(f"Property not found: {property_id}\n")
            raise typer.Exit(code=1)
        console.print(f"[error]Property not found:[/] {property_id}")
        raise typer.Exit(code=1)

    if json_output:
        print(json.dumps(prop.model_dump(mode="json"), indent=2))
        raise typer.Exit(code=0)

    console.print(BRAND_HEADER)
    console.print()
    console.print(f"[heading]{prop.name}[/] [muted]({prop.id})[/]")
    console.print()
    console.print(f"  {'Status':<18} {_status_style(prop.status)}")
    console.print(f"  {'Revision':<18} {prop.revision}")
    console.print(f"  {'Source':<18} {prop.source.value}")
    console.print(f"  {'Invariant Type':<18} [brand]{prop.oracle.evaluator_kind}[/]")
    console.print(f"  {'Stable Key':<18} [muted]{prop.stable_key}[/]")
    console.print()
    console.print("[heading]Description[/]")
    console.print(f"  {prop.description}")
    console.print()
    if prop.rationale:
        console.print("[heading]Rationale[/]")
        console.print(f"  [muted]{prop.rationale}[/]")
        console.print()

    if prop.evidence:
        console.print("[heading]Supporting Evidence[/]")
        for ev in prop.evidence:
            loc = f" @ {ev.file_path}" + (f":{ev.line}" if ev.line else "")
            console.print(f"  - [brand]{ev.evidence_type.value}:[/] {ev.description}{loc}")
        console.print()

    console.print(f"[path]File: {store.property_path(prop.id)}[/]")
    console.print()


@properties_app.command("approve")
def approve_property(
    property_id: Annotated[
        str,
        typer.Argument(help="Property ID (e.g. 'VPROP-01...') or property name slug."),
    ],
    path: Annotated[
        Path | None,
        typer.Option(
            "--path",
            "-p",
            help="Target repository root path (defaults to current directory).",
        ),
    ] = None,
) -> None:
    """Approve a candidate property as an active verification baseline."""
    target_root = (path or Path.cwd()).resolve()
    store = PropertyStore(target_root)
    try:
        prop = store.approve(property_id)
        console.print(
            f"{OK} [ok]Approved property (rev {prop.revision}):[/] {prop.name} [muted]({prop.id})[/]"
        )
        console.print(f"[path]Updated: {store.property_path(prop.id)}[/]")
    except PropertyNotFoundError:
        console.print(f"[error]Property not found:[/] {property_id}")
        raise typer.Exit(code=1) from None


@properties_app.command("reject")
def reject_property(
    property_id: Annotated[
        str,
        typer.Argument(help="Property ID (e.g. 'VPROP-01...') or property name slug."),
    ],
    path: Annotated[
        Path | None,
        typer.Option(
            "--path",
            "-p",
            help="Target repository root path (defaults to current directory).",
        ),
    ] = None,
) -> None:
    """Reject a candidate property."""
    target_root = (path or Path.cwd()).resolve()
    store = PropertyStore(target_root)
    try:
        prop = store.reject(property_id)
        console.print(
            f"{OK} [muted]Rejected property (rev {prop.revision}):[/] {prop.name} [muted]({prop.id})[/]"
        )
        console.print(f"[path]Updated: {store.property_path(prop.id)}[/]")
    except PropertyNotFoundError:
        console.print(f"[error]Property not found:[/] {property_id}")
        raise typer.Exit(code=1) from None
