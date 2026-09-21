"""
``viveka inspect`` — safely scan repository structure, analyze Python AST, and infer capabilities.

Phase 2, 3, & 4 implementation:
  - Discovers files safely via Phase 2 scanner.
  - With --dry-run: shows file discovery inventory without AST analysis.
  - Normal inspect: performs structural Python AST analysis (Phase 3) and
    deterministic capability classification, trust boundaries, and capability graph (Phase 4).
  - Supports machine-readable --json output with schema_version: 1.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from viveka.capabilities import (
    CapabilityAnalysisResult,
    build_capability_graph,
    classify_capabilities,
    infer_trust_boundaries,
)
from viveka.core.config import load_config
from viveka.core.errors import ConfigurationError
from viveka.core.paths import project_config_path
from viveka.inspection.analyzer import analyze_python_repository
from viveka.inspection.models import Decision, Reason
from viveka.inspection.scanner import scan_repository
from viveka.reporting.console import BRAND_HEADER, OK, WARN, console


def _format_reason(reason: Reason) -> str:
    """Format a Reason enum into a readable label."""
    labels = {
        Reason.DEFAULT_EXCLUSION: "default exclusion",
        Reason.GITIGNORE: ".gitignore",
        Reason.VIVEKAIGNORE: ".vivekaignore",
        Reason.CLI_EXCLUDE: "CLI exclude",
        Reason.SENSITIVE_FILE: "sensitive file",
        Reason.BINARY_FILE: "binary file",
        Reason.FILE_TOO_LARGE: "file too large",
        Reason.SYMLINK: "symlink",
        Reason.BROKEN_SYMLINK: "broken symlink",
        Reason.OUTSIDE_ROOT: "outside repository",
        Reason.SYMLINK_LOOP: "symlink loop",
        Reason.INACCESSIBLE: "inaccessible",
        Reason.USER_STATE: "user state",
        Reason.NOT_INCLUDED: "not included",
        Reason.INCLUDED: "selected",
    }
    return labels.get(reason, str(reason))


def inspect_command(
    path: Annotated[
        Path | None,
        typer.Argument(
            help="Target repository root path (defaults to current directory).",
            file_okay=False,
            exists=False,
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-d",
            help="Show files that would be inspected without performing semantic/AST analysis.",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            "-j",
            help="Output complete scan and analysis results as machine-readable JSON.",
        ),
    ] = False,
    include: Annotated[
        list[str] | None,
        typer.Option(
            "--include",
            "-i",
            help="Include only files matching this glob pattern (can be specified multiple times).",
        ),
    ] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option(
            "--exclude",
            "-e",
            help="Exclude files matching this glob pattern (can be specified multiple times).",
        ),
    ] = None,
    follow_symlinks: Annotated[
        bool | None,
        typer.Option(
            "--follow-symlinks/--no-follow-symlinks",
            help="Override follow_symlinks setting.",
        ),
    ] = None,
    max_file_size_kb: Annotated[
        int | None,
        typer.Option(
            "--max-file-size-kb",
            help="Maximum file size in KB to inspect.",
        ),
    ] = None,
    offline: Annotated[
        bool,
        typer.Option(
            "--offline",
            help="Enforce offline inspection (no external network calls).",
        ),
    ] = False,
) -> None:
    """Inspect repository structure and discover eligible files safely."""
    target_root = (path or Path.cwd()).resolve()

    if not target_root.exists():
        if json_output:
            sys.stderr.write(f"Repository not found: {target_root}\n")
            raise typer.Exit(code=2)
        console.print(f"[error]Repository not found:[/] {target_root}")
        raise typer.Exit(code=2)

    if not target_root.is_dir():
        if json_output:
            sys.stderr.write(f"Path is not a directory: {target_root}\n")
            raise typer.Exit(code=2)
        console.print(f"[error]Path is not a directory:[/] {target_root}")
        raise typer.Exit(code=2)

    # Attempt to load configuration if present
    cfg_file = project_config_path(target_root)
    cfg = None
    if cfg_file.is_file():
        try:
            cfg = load_config(cfg_file)
        except ConfigurationError:
            pass  # Fall back to safe defaults

    # 1. Run safe Phase 2 scan
    scan_summary = scan_repository(
        root=target_root,
        config=cfg,
        cli_includes=include,
        cli_excludes=exclude,
        follow_symlinks=follow_symlinks,
        max_file_size_kb=max_file_size_kb,
    )

    # 2. Dry-run Mode (no AST parsing)
    if dry_run:
        if json_output:
            envelope = {
                "schema_version": 1,
                "scan": scan_summary.model_dump(),
                "static_analysis": None,
                "capability_analysis": None,
            }
            print(json.dumps(envelope, indent=2))
            raise typer.Exit(code=0)

        console.print(BRAND_HEADER)
        console.print()
        console.print(f"[heading]Repository[/]\n{scan_summary.root}")
        console.print()
        console.print("[info]Scanning safely... (dry-run)[/]")
        console.print()

        console.print("[heading]Selected for future inspection[/]")
        console.print()
        if scan_summary.selected_files:
            for f in scan_summary.selected_files:
                hint_str = f" [muted]({f.language_hint})[/]" if f.language_hint else ""
                console.print(f"  {OK} {f.relative_path}{hint_str}")
        else:
            console.print("  [muted](no files selected)[/]")
        console.print()

        excluded_or_skipped = [f for f in scan_summary.all_files if f.decision != Decision.INCLUDE]
        if excluded_or_skipped:
            console.print("[heading]Excluded[/]")
            console.print()
            for f in excluded_or_skipped:
                reason_label = _format_reason(f.reason)
                console.print(f"  [muted]{f.relative_path:<36}[/] [info]{reason_label}[/]")
            console.print()

        if scan_summary.warnings:
            console.print("[warn]Warnings[/]")
            console.print()
            for w in scan_summary.warnings:
                console.print(f"  {WARN} {w}")
            console.print()

        console.print("[heading]Summary[/]")
        console.print()
        console.print(f"  {'Files seen':<26} {scan_summary.files_seen}")
        console.print(f"  {'Selected':<26} [ok]{scan_summary.files_selected}[/]")
        console.print(f"  {'Excluded':<26} [muted]{scan_summary.files_excluded}[/]")
        if scan_summary.sensitive_files_detected:
            console.print(f"  {'Sensitive':<26} [warn]{scan_summary.sensitive_files_detected}[/]")
        if scan_summary.binary_files_skipped:
            console.print(f"  {'Binary':<26} [muted]{scan_summary.binary_files_skipped}[/]")
        if scan_summary.oversized_files_skipped:
            console.print(f"  {'Oversized':<26} [muted]{scan_summary.oversized_files_skipped}[/]")
        if scan_summary.symlinks_skipped:
            console.print(f"  {'Symlinks':<26} [muted]{scan_summary.symlinks_skipped}[/]")
        console.print()
        console.print("[ok]No file contents were executed.[/]")
        console.print()
        raise typer.Exit(code=0)

    # 3. Phase 3 Static Analysis
    analysis_result = analyze_python_repository(target_root, scan_summary)

    # 4. Phase 4 Capability Analysis
    capabilities, cap_stats = classify_capabilities(analysis_result)
    capability_graph = build_capability_graph(analysis_result, capabilities)
    trust_boundaries = infer_trust_boundaries(capabilities)
    cap_stats.total_trust_boundaries = len(trust_boundaries)
    cap_stats.total_graph_nodes = len(capability_graph.nodes)
    cap_stats.total_graph_edges = len(capability_graph.edges)

    capability_result = CapabilityAnalysisResult(
        capabilities=capabilities,
        trust_boundaries=trust_boundaries,
        graph=capability_graph,
        statistics=cap_stats,
    )

    # JSON Output Mode
    if json_output:
        envelope = {
            "schema_version": 1,
            "scan": scan_summary.model_dump(),
            "static_analysis": analysis_result.model_dump(),
            "capability_analysis": capability_result.model_dump(),
        }
        print(json.dumps(envelope, indent=2))
        raise typer.Exit(code=0)

    # Full Human-readable Rich Output Mode
    console.print(BRAND_HEADER)
    console.print()
    console.print(f"[heading]Repository[/]\n{scan_summary.root}")
    console.print()
    console.print("[info]Scanning safely...[/]")
    console.print()

    # Python Static Analysis stats
    console.print("[heading]Python Static Analysis[/]")
    console.print()
    console.print(f"  {'Modules analyzed':<26} {analysis_result.files_analyzed}")
    console.print(f"  {'Functions':<26} {analysis_result.total_functions}")
    console.print(f"  {'Classes':<26} {analysis_result.total_classes}")
    console.print(f"  {'Imports':<26} {analysis_result.total_imports}")
    console.print(f"  {'Tool candidates':<26} [property]{len(analysis_result.tool_candidates)}[/]")
    console.print(f"  {'Entrypoint candidates':<26} {len(analysis_result.entrypoint_candidates)}")
    if analysis_result.parse_failures:
        console.print(f"  {'Parse failures':<26} [error]{len(analysis_result.parse_failures)}[/]")
    else:
        console.print(f"  {'Parse failures':<26} 0")
    console.print()

    # Framework hints
    if analysis_result.framework_hints:
        console.print("[heading]Framework hints[/]")
        console.print()
        for hint in analysis_result.framework_hints:
            console.print(f"  [brand]{hint.framework_name}[/]")
            for ev in hint.evidence[:3]:
                console.print(f"    [muted]evidence:[/] {ev}")
            console.print()

    # Tool candidates
    if analysis_result.tool_candidates:
        console.print("[heading]Tool candidates[/]")
        console.print()
        for tc in analysis_result.tool_candidates:
            console.print(f"  [property]{tc.symbol_name}[/]")
            console.print(f"    [path]{tc.file_path}:{tc.line}[/]")
            console.print(f"    [muted]evidence:[/] {tc.evidence}")
            console.print()

    # Entrypoint candidates
    if analysis_result.entrypoint_candidates:
        console.print("[heading]Likely entrypoints[/]")
        console.print()
        for ep in analysis_result.entrypoint_candidates:
            if ep.route_method and ep.route_path:
                label = f"{ep.route_method} {ep.route_path}"
            else:
                label = ep.symbol_or_path
            console.print(f"  [heading]{label}[/]")
            console.print(f"    [path]{ep.file_path}:{ep.line}[/]")
            console.print(f"    [muted]evidence:[/] {ep.evidence}")
            console.print()

    # Capability Analysis stats
    console.print("[heading]Capability Analysis (Static)[/]")
    console.print()
    console.print(f"  {'Capabilities inferred':<26} {len(capabilities)}")
    console.print(f"  {'Trust boundaries':<26} {len(trust_boundaries)}")
    console.print(f"  {'Graph nodes':<26} {len(capability_graph.nodes)}")
    console.print(f"  {'Graph edges':<26} {len(capability_graph.edges)}")
    console.print()

    # Inferred Capabilities details
    if capabilities:
        console.print("[heading]Inferred Capabilities[/]")
        console.print()
        for cap in capabilities:
            tag_str = ", ".join(t.value for t in cap.tags)
            console.print(f"  [brand]{cap.source_symbol}[/] [muted]({cap.id})[/]")
            console.print(f"    [path]{cap.source_file}:{cap.source_line}[/]")
            console.print(f"    [property]tags:[/] {tag_str}")
            console.print(
                f"    [muted]side_effect:[/] {cap.side_effect.value}  "
                f"[muted]externality:[/] {cap.externality.value}  "
                f"[muted]trust_role:[/] {cap.trust_role.value}"
            )
            console.print()

    # Trust Boundaries details
    if trust_boundaries:
        console.print("[heading]Trust Boundaries (Static)[/]")
        console.print()
        for tb in trust_boundaries:
            console.print(f"  [heading]{tb.id}[/] [muted]({tb.boundary_type})[/]")
            console.print(f"    {tb.source} -> {tb.destination}")
            console.print()

    # Parse failures if any
    if analysis_result.parse_failures:
        console.print("[error]Parse Failures[/]")
        console.print()
        for pf in analysis_result.parse_failures:
            loc = f":{pf.line}" if pf.line else ""
            console.print(
                f"  [error]✗[/] [path]{pf.file_path}{loc}[/]: {pf.error_type} — {pf.message}"
            )
        console.print()

    # Warnings if any
    if scan_summary.warnings:
        console.print("[warn]Warnings[/]")
        console.print()
        for w in scan_summary.warnings:
            console.print(f"  {WARN} {w}")
        console.print()

    console.print("[ok]No file contents were executed.[/]")
    console.print()

    raise typer.Exit(code=0)
