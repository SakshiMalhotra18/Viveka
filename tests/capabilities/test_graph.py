"""Tests for viveka.capabilities.graph — graph construction."""

from __future__ import annotations

from tests.capabilities.conftest import (
    make_call,
    make_function,
    make_import,
    make_module,
    make_static_result,
)
from viveka.capabilities.classifier import classify_capabilities
from viveka.capabilities.graph import build_capability_graph


class TestGraphConstruction:
    def test_empty_result_produces_empty_graph(self) -> None:
        result = make_static_result(modules=[])
        caps, _ = classify_capabilities(result)
        graph = build_capability_graph(result, caps)
        assert graph.nodes == []
        assert graph.edges == []

    def test_module_nodes_created(self) -> None:
        func = make_function("noop", calls=[])
        mod = make_module("agent.py", "agent", functions=[func])
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        graph = build_capability_graph(result, caps)

        module_nodes = [n for n in graph.nodes if n.node_type == "module"]
        assert len(module_nodes) >= 1
        assert any(n.file_path == "agent.py" for n in module_nodes)

    def test_capability_nodes_created(self) -> None:
        func = make_function(
            "run_cmd",
            calls=[make_call("subprocess.run(", line=5)],
        )
        mod = make_module(
            "exec.py",
            "exec_mod",
            functions=[func],
            imports=[make_import("subprocess")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        graph = build_capability_graph(result, caps)

        cap_nodes = [n for n in graph.nodes if n.node_type == "capability"]
        assert len(cap_nodes) >= 1

    def test_has_capability_edges_exist(self) -> None:
        func = make_function(
            "run_cmd",
            calls=[make_call("subprocess.run(", line=5)],
        )
        mod = make_module(
            "exec.py",
            "exec_mod",
            functions=[func],
            imports=[make_import("subprocess")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        graph = build_capability_graph(result, caps)

        has_cap_edges = [e for e in graph.edges if e.edge_type == "has_capability"]
        assert len(has_cap_edges) >= 1

    def test_symbol_nodes_have_correct_type(self) -> None:
        func = make_function("helper", calls=[])
        mod = make_module("utils.py", "utils", functions=[func])
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        graph = build_capability_graph(result, caps)

        sym_nodes = [n for n in graph.nodes if n.node_type == "symbol"]
        assert any(n.label == "helper" for n in sym_nodes)

    def test_graph_node_ids_are_unique(self) -> None:
        func1 = make_function("func_a", calls=[make_call("subprocess.run(", line=5)])
        func2 = make_function("func_b", calls=[make_call("os.remove(", line=8)])
        mod = make_module(
            "mixed.py",
            "mixed",
            functions=[func1, func2],
            imports=[make_import("subprocess"), make_import("os")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        graph = build_capability_graph(result, caps)

        ids = [n.id for n in graph.nodes]
        assert len(ids) == len(set(ids)), "Graph node IDs must be unique"

    def test_graph_nodes_list_is_serializable(self) -> None:
        """Ensure graph serializes to dict without errors (for JSON envelope)."""
        func = make_function(
            "write_data",
            calls=[make_call("write_text(", line=5)],
        )
        mod = make_module("output.py", "output", functions=[func])
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        graph = build_capability_graph(result, caps)

        dumped = graph.model_dump()
        assert "nodes" in dumped
        assert "edges" in dumped
