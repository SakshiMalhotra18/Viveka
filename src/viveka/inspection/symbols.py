"""
Tool candidates, entrypoint candidates, and static import graph builder.

Discovers structural candidates without executing or importing any target code.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from viveka.inspection.python_models import (
    Confidence,
    EntryPointCandidate,
    LocalImportEdge,
    PythonModule,
    ToolCandidate,
)

# Standard library modules in Python (for separating external vs local imports)
_STDLIB_MODULES: frozenset[str] = frozenset(sys.stdlib_module_names)

_ROUTE_PATTERN = re.compile(
    r"""(?:app|router|api_router)\.(get|post|put|delete|patch)\(\s*["']([^"']+)["']""",
    re.IGNORECASE,
)


def detect_tool_candidates(modules: list[PythonModule]) -> list[ToolCandidate]:
    """Detect functions and methods that structurally look like AI agent tools."""
    candidates: list[ToolCandidate] = []

    for mod in modules:
        if mod.parse_status != "ok":
            continue

        all_functions = list(mod.functions)
        for cls in mod.classes:
            all_functions.extend(cls.methods)

        for fn in all_functions:
            # 1. Check decorators (High confidence)
            found_decorator = False
            for dec in fn.decorators:
                d_name = dec.name.lower()
                if (
                    d_name in ("tool", "function_tool")
                    or "mcp.tool" in d_name
                    or "agent.tool" in d_name
                ):
                    candidates.append(
                        ToolCandidate(
                            symbol_name=fn.name,
                            qualified_name=fn.qualified_name,
                            file_path=mod.path,
                            line=fn.line_start,
                            decorator_name=dec.name,
                            evidence=f"decorator @{dec.name}",
                            confidence=Confidence.HIGH,
                        )
                    )
                    found_decorator = True
                    break

            if found_decorator:
                continue

            # 2. Check filename heuristics (Medium confidence)
            path_lower = mod.path.lower()
            if ("tool" in path_lower or "action" in path_lower) and fn.docstring_summary:
                if not fn.name.startswith("_"):
                    candidates.append(
                        ToolCandidate(
                            symbol_name=fn.name,
                            qualified_name=fn.qualified_name,
                            file_path=mod.path,
                            line=fn.line_start,
                            decorator_name=None,
                            evidence=f"public function in tool file with docstring: '{fn.docstring_summary}'",
                            confidence=Confidence.MEDIUM,
                        )
                    )

    # Sort deterministically
    candidates.sort(key=lambda c: (c.file_path, c.line, c.symbol_name))
    return candidates


def detect_entrypoint_candidates(modules: list[PythonModule]) -> list[EntryPointCandidate]:
    """Detect functions, routes, and workflows that look like application entrypoints."""
    candidates: list[EntryPointCandidate] = []

    for mod in modules:
        if mod.parse_status != "ok":
            continue

        all_functions = list(mod.functions)
        for cls in mod.classes:
            all_functions.extend(cls.methods)

        # 1. Route decorators on functions (High confidence)
        for fn in all_functions:
            for dec in fn.decorators:
                match = _ROUTE_PATTERN.search(dec.raw_text)
                if match:
                    method = match.group(1).upper()
                    route_path = match.group(2)
                    candidates.append(
                        EntryPointCandidate(
                            entrypoint_type="fastapi_route",
                            symbol_or_path=fn.name,
                            file_path=mod.path,
                            line=dec.line,
                            route_method=method,
                            route_path=route_path,
                            evidence=f"{method} {route_path}",
                            confidence=Confidence.HIGH,
                        )
                    )

        # 2. StateGraph / MCP server creation in module or function calls (High confidence)
        all_calls = list(mod.calls)
        for fn in all_functions:
            all_calls.extend(fn.calls)

        for call in all_calls:
            if "StateGraph" in call.callee or "MessageGraph" in call.callee:
                ep_symbol = call.containing_symbol or "StateGraph"
                candidates.append(
                    EntryPointCandidate(
                        entrypoint_type="stategraph",
                        symbol_or_path=ep_symbol,
                        file_path=mod.path,
                        line=call.line,
                        evidence=f"instantiation {call.callee}(...)",
                        confidence=Confidence.HIGH,
                    )
                )
            elif "FastMCP" in call.callee or "Server" in call.callee:
                candidates.append(
                    EntryPointCandidate(
                        entrypoint_type="mcp_server",
                        symbol_or_path=call.callee,
                        file_path=mod.path,
                        line=call.line,
                        evidence=f"server initialization {call.callee}(...)",
                        confidence=Confidence.HIGH,
                    )
                )

        # 3. Standard main function heuristic (Medium confidence)
        for fn in mod.functions:
            if fn.name in ("main", "run", "serve", "start_agent") and not candidates:
                candidates.append(
                    EntryPointCandidate(
                        entrypoint_type="cli_main",
                        symbol_or_path=fn.name,
                        file_path=mod.path,
                        line=fn.line_start,
                        evidence=f"main execution function '{fn.name}'",
                        confidence=Confidence.MEDIUM,
                    )
                )

    # Sort deterministically
    candidates.sort(key=lambda c: (c.file_path, c.line, c.symbol_or_path))
    return candidates


def build_import_graph(
    modules: list[PythonModule],
) -> tuple[list[LocalImportEdge], list[str]]:
    """Construct lightweight local import graph and collect external packages."""
    # Map module_name for fast lookup
    module_by_name: dict[str, PythonModule] = {m.module_name: m for m in modules}

    local_edges: list[LocalImportEdge] = []
    external_pkgs: set[str] = set()

    for mod in modules:
        if mod.parse_status != "ok":
            continue

        for imp in mod.imports:
            # 1. Handle relative imports
            if imp.relative_level > 0:
                mod_path_parts = Path(mod.path).parts[:-1]  # directory of importing file
                # Climb up levels
                up_levels = imp.relative_level - 1
                if up_levels < len(mod_path_parts):
                    target_dir = mod_path_parts[: len(mod_path_parts) - up_levels]
                    if imp.module:
                        target_mod_parts = (*target_dir, *imp.module.split("."))
                    else:
                        target_mod_parts = (*target_dir, imp.imported_name)
                    target_dotted = ".".join(target_mod_parts)

                    target_mod = module_by_name.get(target_dotted)
                    if target_mod:
                        local_edges.append(
                            LocalImportEdge(
                                source_file=mod.path,
                                target_file=target_mod.path,
                                imported_symbol=imp.imported_name or imp.module,
                            )
                        )
                continue

            # 2. Absolute imports
            base_mod = imp.module.split(".")[0] if imp.module else imp.imported_name.split(".")[0]
            if not base_mod:
                continue

            # Check if this matches a local module
            target_mod = module_by_name.get(imp.module)
            if not target_mod and imp.module:
                # Try prefix matches
                for name, cand in module_by_name.items():
                    if name.endswith(imp.module):
                        target_mod = cand
                        break

            if target_mod:
                local_edges.append(
                    LocalImportEdge(
                        source_file=mod.path,
                        target_file=target_mod.path,
                        imported_symbol=imp.imported_name or imp.module,
                    )
                )
            else:
                # External import (skip standard library)
                if base_mod not in _STDLIB_MODULES:
                    external_pkgs.add(base_mod)

    # Sort deterministically
    local_edges.sort(key=lambda e: (e.source_file, e.target_file, e.imported_symbol))
    sorted_externals = sorted(external_pkgs)

    return local_edges, sorted_externals
