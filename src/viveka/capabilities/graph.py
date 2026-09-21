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
    # 7. possible_interaction edges between capability-bearing symbols
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
