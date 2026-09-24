"""
Static capability graph builder for VIVEKA Phase 4.

Constructs a :class:`~viveka.capabilities.models.CapabilityGraph` from:
  - Phase 3 :class:`~viveka.inspection.python_models.StaticAnalysisResult`
  - Phase 4 :class:`~viveka.capabilities.models.Capability` list

Node types:
  - ``entrypoint``   — detected application entrypoints (routes, CLI mains, etc.)
  - ``tool``         — symbols classified as agent tools
  - ``symbol``       — other functions / classes in the codebase
  - ``capability``   — a VCAP capability node
  - ``module``       — a Python source module

Edge types:
  - ``calls``               — static call relationship (Phase 3 evidence)
  - ``has_capability``      — symbol → capability
  - ``exposes``             — entrypoint or tool → symbol it delegates to
  - ``imports``             — module → module (from local import edges)
  - ``possible_interaction``— inferred flow between two capability-bearing symbols
"""

from __future__ import annotations

from viveka.capabilities.models import (
    Capability,
    CapabilityGraph,
    GraphEdge,
    GraphNode,
)
from viveka.inspection.python_models import StaticAnalysisResult

# ---------------------------------------------------------------------------
# Node helpers
# ---------------------------------------------------------------------------


def _symbol_node_id(qualified_name: str) -> str:
    return f"sym:{qualified_name}"


def _module_node_id(path: str) -> str:
    return f"mod:{path}"


def _cap_node_id(cap_id: str) -> str:
    return f"cap:{cap_id}"


def _entrypoint_node_id(symbol_or_path: str, ep_type: str) -> str:
    return f"ep:{ep_type}:{symbol_or_path}"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_capability_graph(
    static_result: StaticAnalysisResult,
    capabilities: list[Capability],
) -> CapabilityGraph:
    """Build a directed static capability graph.

    Args:
        static_result: Phase 3 structural analysis output.
        capabilities:  Phase 4 classified capabilities.

    Returns:
        A :class:`CapabilityGraph` containing nodes and edges.
    """
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    # -----------------------------------------------------------------------
    # 1. Module nodes
    # -----------------------------------------------------------------------
    for module in static_result.modules:
        if module.parse_status != "ok":
            continue
        node_id = _module_node_id(module.path)
        nodes[node_id] = GraphNode(
            id=node_id,
            label=module.module_name,
            node_type="module",
            file_path=module.path,
            properties={"parse_status": module.parse_status},
        )

    # -----------------------------------------------------------------------
    # 2. Module-level import edges
    # -----------------------------------------------------------------------
    for edge in static_result.local_import_edges:
        src_id = _module_node_id(edge.source_file)
        tgt_id = _module_node_id(edge.target_file)
        if src_id not in nodes:
            nodes[src_id] = GraphNode(
                id=src_id,
                label=edge.source_file,
                node_type="module",
                file_path=edge.source_file,
            )
        if tgt_id not in nodes:
            nodes[tgt_id] = GraphNode(
                id=tgt_id,
                label=edge.target_file,
                node_type="module",
                file_path=edge.target_file,
            )
        edges.append(
            GraphEdge(
                source=src_id,
                target=tgt_id,
                edge_type="imports",
                evidence=f"imports {edge.imported_symbol}",
                confidence="high",
            )
        )

    # -----------------------------------------------------------------------
    # 3. Tool candidate nodes
    # -----------------------------------------------------------------------
    for tc in static_result.tool_candidates:
        node_id = _symbol_node_id(tc.qualified_name)
        nodes[node_id] = GraphNode(
            id=node_id,
            label=tc.symbol_name,
            node_type="tool",
            file_path=tc.file_path,
            line=tc.line,
            properties={
                "confidence": tc.confidence,
                "evidence": tc.evidence,
                **({"decorator": tc.decorator_name} if tc.decorator_name else {}),
            },
        )

    # -----------------------------------------------------------------------
    # 4. Entrypoint nodes
    # -----------------------------------------------------------------------
    for ep in static_result.entrypoint_candidates:
        node_id = _entrypoint_node_id(ep.symbol_or_path, ep.entrypoint_type)
        label = ep.symbol_or_path
        if ep.route_method and ep.route_path:
            label = f"{ep.route_method} {ep.route_path}"
        nodes[node_id] = GraphNode(
            id=node_id,
            label=label,
            node_type="entrypoint",
            file_path=ep.file_path,
            line=ep.line,
            properties={
                "entrypoint_type": ep.entrypoint_type,
                "confidence": ep.confidence,
            },
        )

    # -----------------------------------------------------------------------
    # 5. Symbol nodes from all functions (not yet added as tools)
    # -----------------------------------------------------------------------
    for module in static_result.modules:
        if module.parse_status != "ok":
            continue
        all_funcs = list(module.functions)
        for cls in module.classes:
            all_funcs.extend(cls.methods)

        for func in all_funcs:
            node_id = _symbol_node_id(func.qualified_name)
            if node_id not in nodes:
                nodes[node_id] = GraphNode(
                    id=node_id,
                    label=func.name,
                    node_type="symbol",
                    file_path=module.path,
                    line=func.line_start,
                    properties={"is_async": str(func.is_async)},
                )

        # Static call edges between symbols in the same module
        for func in all_funcs:
            src_id = _symbol_node_id(func.qualified_name)
            for call in func.calls:
                # Try to find a local symbol with this name
                tgt_qname = call.callee.split("(")[0].strip()
                tgt_id = _symbol_node_id(tgt_qname)
                if tgt_id in nodes:
                    edges.append(
                        GraphEdge(
                            source=src_id,
                            target=tgt_id,
                            edge_type="calls",
                            evidence=f"{func.name} calls {call.callee}",
                            confidence="medium",
                        )
                    )

    # -----------------------------------------------------------------------
    # 6. Capability nodes + has_capability edges
    # -----------------------------------------------------------------------
    for cap in capabilities:
        cap_node_id = _cap_node_id(cap.id)
        tag_labels = ", ".join(str(t) for t in cap.tags[:3])
        nodes[cap_node_id] = GraphNode(
            id=cap_node_id,
            label=cap.name,
            node_type="capability",
            file_path=cap.source_file,
            line=cap.source_line,
            properties={
                "tags": tag_labels,
                "confidence": cap.confidence,
                "side_effect": str(cap.side_effect),
                "externality": str(cap.externality),
                "trust_role": str(cap.trust_role),
                **({"rule_id": cap.rule_id} if cap.rule_id else {}),
            },
        )
        sym_id = _symbol_node_id(cap.source_symbol)
        if sym_id not in nodes:
            nodes[sym_id] = GraphNode(
                id=sym_id,
                label=cap.source_symbol,
                node_type="symbol",
                file_path=cap.source_file,
                line=cap.source_line,
            )
        edges.append(
            GraphEdge(
                source=sym_id,
                target=cap_node_id,
                edge_type="has_capability",
                evidence=f"rule {cap.rule_id}",
                confidence=cap.confidence,
            )
        )

    # -----------------------------------------------------------------------
    # 7. LangGraph node registrations & workflow edges
    # -----------------------------------------------------------------------
    node_name_to_sym: dict[str, str] = {}

    for module in static_result.modules:
        if module.parse_status != "ok":
            continue

        all_calls = list(module.calls)
        for fn in module.functions:
            all_calls.extend(fn.calls)
        for cls in module.classes:
            for meth in cls.methods:
                all_calls.extend(meth.calls)

        # 1. First pass: find add_node calls
        for call in all_calls:
            if call.callee.endswith(".add_node") or call.callee == "add_node":
                if len(call.positional_args) >= 2:
                    node_name = call.positional_args[0].strip("'\"")
                    callable_expr = call.positional_args[1].strip()
                elif len(call.positional_args) == 1:
                    node_name = call.positional_args[0].strip("'\"")
                    callable_expr = node_name
                else:
                    continue

                callable_sym = callable_expr.split(".")[-1]
                sym_id = _symbol_node_id(callable_sym)
                if sym_id not in nodes:
                    matched = False
                    for nid in nodes:
                        if nid.endswith(f":{callable_sym}") or nid == f"sym:{callable_expr}":
                            sym_id = nid
                            matched = True
                            break
                    if not matched:
                        nodes[sym_id] = GraphNode(
                            id=sym_id,
                            label=callable_sym,
                            node_type="symbol",
                            file_path=module.path,
                            line=call.line,
                        )

                node_name_to_sym[node_name] = sym_id

                ep_found = False
                for ep in static_result.entrypoint_candidates:
                    if ep.entrypoint_type == "stategraph" and ep.file_path == module.path:
                        ep_id = _entrypoint_node_id(ep.symbol_or_path, ep.entrypoint_type)
                        edges.append(
                            GraphEdge(
                                source=ep_id,
                                target=sym_id,
                                edge_type="exposes",
                                evidence=f"LangGraph registered node '{node_name}' -> {callable_expr}",
                                confidence="high",
                            )
                        )
                        ep_found = True

                if not ep_found:
                    ep_symbol = call.containing_symbol or "StateGraph"
                    ep_id = _entrypoint_node_id(ep_symbol, "stategraph")
                    if ep_id not in nodes:
                        nodes[ep_id] = GraphNode(
                            id=ep_id,
                            label=f"StateGraph ({ep_symbol})",
                            node_type="entrypoint",
                            file_path=module.path,
                            line=call.line,
                            properties={"entrypoint_type": "stategraph", "confidence": "high"},
                        )
                    edges.append(
                        GraphEdge(
                            source=ep_id,
                            target=sym_id,
                            edge_type="exposes",
                            evidence=f"LangGraph registered node '{node_name}' -> {callable_expr}",
                            confidence="high",
                        )
                    )

        # 2. Second pass: find add_edge and add_conditional_edges calls
        for call in all_calls:
            if call.callee.endswith(".add_edge") or call.callee == "add_edge":
                if len(call.positional_args) >= 2:
                    src_node = call.positional_args[0].strip("'\"")
                    tgt_node = call.positional_args[1].strip("'\"")
                    src_sym_id = node_name_to_sym.get(src_node)
                    tgt_sym_id = node_name_to_sym.get(tgt_node)
                    if src_sym_id and tgt_sym_id and src_sym_id != tgt_sym_id:
                        edges.append(
                            GraphEdge(
                                source=src_sym_id,
                                target=tgt_sym_id,
                                edge_type="calls",
                                evidence=f"LangGraph workflow edge: {src_node} -> {tgt_node}",
                                confidence="high",
                            )
                        )

            elif (
                call.callee.endswith(".add_conditional_edges")
                or call.callee == "add_conditional_edges"
            ):
                if len(call.positional_args) >= 2:
                    import re

                    src_node = call.positional_args[0].strip("'\"")
                    src_sym_id = node_name_to_sym.get(src_node)

                    # Extract router function if present
                    router_expr = call.positional_args[1].strip()
                    router_sym = router_expr.split(".")[-1]
                    router_sym_id = node_name_to_sym.get(router_sym) or _symbol_node_id(router_sym)
                    if router_sym_id not in nodes:
                        for nid in nodes:
                            if nid.endswith(f":{router_sym}"):
                                router_sym_id = nid
                                break
                        else:
                            router_sym_id = None

                    # If source and router exist, link src -> router
                    if src_sym_id and router_sym_id and src_sym_id != router_sym_id:
                        edges.append(
                            GraphEdge(
                                source=src_sym_id,
                                target=router_sym_id,
                                edge_type="calls",
                                evidence=f"LangGraph conditional route: {src_node} -> {router_sym}",
                                confidence="high",
                            )
                        )

                    # Extract candidate target nodes from arguments
                    all_target_names: list[str] = []
                    for arg_str in call.positional_args[1:]:
                        quoted_names = re.findall(r"['\"]([^'\"]+)['\"]", arg_str)
                        all_target_names.extend(quoted_names)

                    for tgt_node in all_target_names:
                        tgt_sym_id = node_name_to_sym.get(tgt_node)
                        if tgt_sym_id:
                            if src_sym_id and src_sym_id != tgt_sym_id:
                                edges.append(
                                    GraphEdge(
                                        source=src_sym_id,
                                        target=tgt_sym_id,
                                        edge_type="calls",
                                        evidence=f"LangGraph conditional edge: {src_node} -> {tgt_node}",
                                        confidence="high",
                                    )
                                )
                            if router_sym_id and router_sym_id != tgt_sym_id:
                                edges.append(
                                    GraphEdge(
                                        source=router_sym_id,
                                        target=tgt_sym_id,
                                        edge_type="calls",
                                        evidence=f"LangGraph conditional edge router: {router_sym} -> {tgt_node}",
                                        confidence="high",
                                    )
                                )

    # -----------------------------------------------------------------------
    # 8. possible_interaction edges between capability-bearing symbols
    # -----------------------------------------------------------------------
    # For each entrypoint, link it to tools it might invoke (same file or
    # via import graph) as "possible_interaction".
    ep_ids = [nid for nid, n in nodes.items() if n.node_type == "entrypoint"]
    tool_ids = [nid for nid, n in nodes.items() if n.node_type == "tool"]

    for ep_id in ep_ids:
        ep_node = nodes[ep_id]
        for tool_id in tool_ids:
            tool_node = nodes[tool_id]
            if ep_node.file_path and tool_node.file_path:
                if ep_node.file_path == tool_node.file_path:
                    edges.append(
                        GraphEdge(
                            source=ep_id,
                            target=tool_id,
                            edge_type="possible_interaction",
                            evidence="same file — entrypoint may invoke tool",
                            confidence="low",
                        )
                    )

    return CapabilityGraph(
        nodes=list(nodes.values()),
        edges=edges,
    )
