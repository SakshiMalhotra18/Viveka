"""Tests for viveka.properties.engine — interaction requirements, stable capability keys, and failure tool filtering."""

from __future__ import annotations

from viveka.capabilities.models import (
    Capability,
    CapabilityAnalysisResult,
    CapabilityEvidence,
    CapabilityGraph,
    CapabilityStatistics,
    GraphEdge,
    GraphNode,
    TrustBoundary,
)
from viveka.capabilities.vocabulary import (
    CapabilityTag,
    Externality,
    Reversibility,
    SideEffect,
    TrustRole,
)
from viveka.properties.engine import capability_key, generate_stable_key, infer_candidate_properties
from viveka.properties.models import FailureHandledOracle, FlowForbiddenOracle
from viveka.properties.vocabulary import PropertyStatus


def _make_cap(
    file_path: str,
    symbol: str,
    rule_id: str,
    tags: list[CapabilityTag],
    trust_role: TrustRole,
    side_effect: SideEffect = SideEffect.MUTATING,
) -> Capability:
    return Capability(
        id=f"VCAP-{symbol}",
        name=symbol,
        source_symbol=symbol,
        source_file=file_path,
        source_line=10,
        tags=tags,
        confidence="high",
        evidence=[
            CapabilityEvidence(
                evidence_type="call",
                value=symbol,
                file_path=file_path,
                line=10,
            )
        ],
        side_effect=side_effect,
        externality=Externality.EXTERNAL,
        reversibility=Reversibility.IRREVERSIBLE,
        trust_role=trust_role,
        rule_id=rule_id,
    )


class TestStableKeys:
    def test_capability_key_path_qualified(self) -> None:
        cap = _make_cap(
            "src/tools.py",
            "refund_order",
            "RULE-FIN-REFUND-001",
            [CapabilityTag.FINANCIAL_WRITE],
            TrustRole.PRIVILEGED_SINK,
        )
        assert capability_key(cap) == "src/tools.py::refund_order"

    def test_stable_property_key_derived_from_capability_keys(self) -> None:
        src_key = "src/tools.py::search_docs"
        sink_key = "src/tools.py::refund_order"
        key = generate_stable_key("PROP-RULE-RET-FIN-001", "forbidden_flow", src_key, sink_key)
        assert (
            key
            == "prop-rule-ret-fin-001:forbidden_flow:src/tools.py::search_docs->src/tools.py::refund_order"
        )


class TestInteractionEvidenceRequirement:
    def test_co_location_alone_does_not_trigger_property(self) -> None:
        """Co-location in the same file/module without graph reachability or trust boundary must NOT trigger flow property."""
        src_cap = _make_cap(
            "src/utils.py",
            "search_docs",
            "RULE-RET-SEARCH-001",
            [CapabilityTag.RETRIEVAL, CapabilityTag.UNTRUSTED_INPUT],
            TrustRole.UNTRUSTED_INGRESS,
            SideEffect.READ_ONLY,
        )
        sink_cap = _make_cap(
            "src/utils.py",
            "refund_order",
            "RULE-FIN-REFUND-001",
            [CapabilityTag.FINANCIAL_WRITE],
            TrustRole.PRIVILEGED_SINK,
            SideEffect.MUTATING,
        )

        # Graph has nodes but NO edges, NO workflow reachability, and NO trust boundary
        graph = CapabilityGraph(
            nodes=[
                GraphNode(id="sym:search_docs", label="search_docs", node_type="symbol"),
                GraphNode(id="sym:refund_order", label="refund_order", node_type="symbol"),
            ],
            edges=[],
        )
        analysis = CapabilityAnalysisResult(
            capabilities=[src_cap, sink_cap],
            trust_boundaries=[],
            graph=graph,
            statistics=CapabilityStatistics(),
        )

        candidates = infer_candidate_properties(analysis)
        flow_props = [c for c in candidates if c.oracle.evaluator_kind == "flow_forbidden"]
        assert len(flow_props) == 0, (
            "Co-location alone must not trigger a cross-capability property"
        )

    def test_graph_edge_interaction_triggers_property(self) -> None:
        """A direct graph edge between source and sink confirms interaction and triggers property."""
        src_cap = _make_cap(
            "src/tools.py",
            "search_docs",
            "RULE-RET-SEARCH-001",
            [CapabilityTag.RETRIEVAL, CapabilityTag.UNTRUSTED_INPUT],
            TrustRole.UNTRUSTED_INGRESS,
            SideEffect.READ_ONLY,
        )
        sink_cap = _make_cap(
            "src/tools.py",
            "refund_order",
            "RULE-FIN-REFUND-001",
            [CapabilityTag.FINANCIAL_WRITE],
            TrustRole.PRIVILEGED_SINK,
            SideEffect.MUTATING,
        )

        # Direct edge in graph
        graph = CapabilityGraph(
            nodes=[
                GraphNode(id="sym:search_docs", label="search_docs", node_type="tool"),
                GraphNode(id="sym:refund_order", label="refund_order", node_type="tool"),
            ],
            edges=[
                GraphEdge(
                    source="sym:search_docs",
                    target="sym:refund_order",
                    edge_type="calls",
                    evidence="search calls refund",
                )
            ],
        )
        analysis = CapabilityAnalysisResult(
            capabilities=[src_cap, sink_cap],
            trust_boundaries=[],
            graph=graph,
            statistics=CapabilityStatistics(),
        )

        candidates = infer_candidate_properties(analysis)
        ret_fin = [c for c in candidates if c.rule_id == "PROP-RULE-RET-FIN-001"]
        assert len(ret_fin) == 1
        prop = ret_fin[0]
        assert isinstance(prop.oracle, FlowForbiddenOracle)
        assert prop.oracle.untrusted_source_key == "src/tools.py::search_docs"
        assert prop.oracle.forbidden_sink_key == "src/tools.py::refund_order"
        assert prop.status == PropertyStatus.CANDIDATE

    def test_trust_boundary_flow_triggers_property(self) -> None:
        """Active trust boundaries linking ingress to agent context and agent context to sink trigger property."""
        src_cap = _make_cap(
            "src/ingress.py",
            "read_webhook",
            "RULE-RET-SEARCH-001",
            [CapabilityTag.RETRIEVAL, CapabilityTag.UNTRUSTED_INPUT],
            TrustRole.UNTRUSTED_INGRESS,
            SideEffect.READ_ONLY,
        )
        sink_cap = _make_cap(
            "src/billing.py",
            "create_refund",
            "RULE-FIN-REFUND-001",
            [CapabilityTag.FINANCIAL_WRITE],
            TrustRole.PRIVILEGED_SINK,
            SideEffect.MUTATING,
        )

        graph = CapabilityGraph(
            nodes=[
                GraphNode(id="sym:read_webhook", label="read_webhook", node_type="tool"),
                GraphNode(id="sym:create_refund", label="create_refund", node_type="tool"),
            ],
            edges=[],
        )
        boundaries = [
            TrustBoundary(
                id="VBOUND-0001",
                boundary_type="untrusted_ingress",
                source="external:untrusted",
                destination="agent:context",
                confidence="high",
                evidence=["read_webhook @ src/ingress.py:10"],
            ),
            TrustBoundary(
                id="VBOUND-0002",
                boundary_type="privileged_sink",
                source="agent:context",
                destination="create_refund",
                confidence="high",
                evidence=["create_refund @ src/billing.py:10"],
            ),
        ]
        analysis = CapabilityAnalysisResult(
            capabilities=[src_cap, sink_cap],
            trust_boundaries=boundaries,
            graph=graph,
            statistics=CapabilityStatistics(),
        )

        candidates = infer_candidate_properties(analysis)
        ret_fin = [c for c in candidates if c.rule_id == "PROP-RULE-RET-FIN-001"]
        assert len(ret_fin) == 1


class TestFailureRuleToolScope:
    def test_exposed_tool_candidate_gets_failure_rule(self) -> None:
        mutating_cap = _make_cap(
            "src/tools.py",
            "refund_order",
            "RULE-FIN-REFUND-001",
            [CapabilityTag.FINANCIAL_WRITE],
            TrustRole.PRIVILEGED_SINK,
            SideEffect.MUTATING,
        )
        # Node has node_type == "tool"
        graph = CapabilityGraph(
            nodes=[GraphNode(id="sym:refund_order", label="refund_order", node_type="tool")],
            edges=[],
        )
        analysis = CapabilityAnalysisResult(
            capabilities=[mutating_cap],
            trust_boundaries=[],
            graph=graph,
            statistics=CapabilityStatistics(),
        )

        candidates = infer_candidate_properties(analysis)
        fail_props = [c for c in candidates if c.rule_id == "PROP-RULE-FAIL-SILENT-001"]
        assert len(fail_props) == 1
        assert isinstance(fail_props[0].oracle, FailureHandledOracle)
        assert fail_props[0].oracle.target_action_key == "src/tools.py::refund_order"

    def test_internal_helper_does_not_get_failure_rule(self) -> None:
        """Internal helper function that is not a tool candidate must NOT get failure handling property."""
        internal_cap = _make_cap(
            "src/utils.py",
            "_internal_writer",
            "RULE-FS-WRITE-001",
            [CapabilityTag.FILESYSTEM_WRITE],
            TrustRole.PRIVILEGED_SINK,
            SideEffect.MUTATING,
        )
        # Node has node_type == "symbol", NOT "tool"
        graph = CapabilityGraph(
            nodes=[
                GraphNode(id="sym:_internal_writer", label="_internal_writer", node_type="symbol")
            ],
            edges=[],
        )
        analysis = CapabilityAnalysisResult(
            capabilities=[internal_cap],
            trust_boundaries=[],
            graph=graph,
            statistics=CapabilityStatistics(),
        )

        candidates = infer_candidate_properties(analysis)
        fail_props = [c for c in candidates if c.rule_id == "PROP-RULE-FAIL-SILENT-001"]
        assert len(fail_props) == 0, "Internal helpers must not get failure properties"
