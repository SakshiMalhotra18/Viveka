"""
Static analysis coordinator for VIVEKA.

Takes Phase 2 ScanSummary, analyzes all selected Python files with AST parsing,
detects framework and tool candidates, and constructs structural static analysis.
"""

from __future__ import annotations

from pathlib import Path

from viveka.inspection.frameworks import detect_framework_hints
from viveka.inspection.models import Decision, ScanSummary
from viveka.inspection.python_ast import parse_python_module
from viveka.inspection.python_models import ParseFailure, PythonModule, StaticAnalysisResult
from viveka.inspection.symbols import (
    build_import_graph,
    detect_entrypoint_candidates,
    detect_tool_candidates,
)


def analyze_python_repository(
    root: Path,
    scan_summary: ScanSummary,
) -> StaticAnalysisResult:
    """Perform structural static analysis on Python files selected by the Phase 2 scanner.

    Args:
        root: Target repository root path.
        scan_summary: Completed ScanSummary from Phase 2 scan_repository.

    Returns:
        Structured :class:`StaticAnalysisResult` containing module ASTs, candidates, and graphs.
    """
    resolved_root = root.resolve()

    # Filter for selected Python files only
    py_files = [
        f
        for f in scan_summary.selected_files
        if f.decision == Decision.INCLUDE and f.language_hint == "python"
    ]

    modules: list[PythonModule] = []
    parse_failures: list[ParseFailure] = []

    for file_info in py_files:
        abs_path = resolved_root / file_info.relative_path
        mod = parse_python_module(abs_path, file_info.relative_path)
        modules.append(mod)
        if mod.syntax_error:
            parse_failures.append(mod.syntax_error)

    # Sort modules deterministically
    modules.sort(key=lambda m: m.path)
    parse_failures.sort(key=lambda p: (p.file_path, p.line or 0))

    # Detect heuristic candidates & build import graph
    framework_hints = detect_framework_hints(modules)
    tool_candidates = detect_tool_candidates(modules)
    entrypoint_candidates = detect_entrypoint_candidates(modules)
    local_edges, external_imports = build_import_graph(modules)

    # Compute aggregate statistics
    total_functions = 0
    total_classes = 0
    total_imports = 0
    total_calls = 0

    for m in modules:
        total_functions += len(m.functions)
        for c in m.classes:
            total_functions += len(c.methods)
            total_classes += 1
        total_imports += len(m.imports)
        total_calls += len(m.calls)
        for f in m.functions:
            total_calls += len(f.calls)
        for c in m.classes:
            for meth in c.methods:
                total_calls += len(meth.calls)

    return StaticAnalysisResult(
        project_root=str(resolved_root),
        files_analyzed=len(py_files),
        modules=modules,
        local_import_edges=local_edges,
        external_imports=external_imports,
        framework_hints=framework_hints,
        tool_candidates=tool_candidates,
        entrypoint_candidates=entrypoint_candidates,
        parse_failures=parse_failures,
        total_functions=total_functions,
        total_classes=total_classes,
        total_imports=total_imports,
        total_calls=total_calls,
    )
