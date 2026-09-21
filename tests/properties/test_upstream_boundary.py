"""Lightweight boundary test for the CapabilityAnalysisResult → PropertyEngine contract."""

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
from viveka.properties.engine import infer_candidate_properties
from viveka.properties.models import FlowForbiddenOracle, Property


def test_capability_analysis_result_to_property_engine_contract() -> None:
    """Verify that PropertyEngine cleanly consumes a synthetic CapabilityAnalysisResult."""
    src_cap = Capability(
        id="VCAP-01SEARCH",
        name="search_knowledge_base [Retrieval]",
        source_symbol="search_knowledge_base",
        source_file="src/tools.py",
        source_line=15,
        tags=[CapabilityTag.RETRIEVAL, CapabilityTag.UNTRUSTED_INPUT],
        confidence="high",
        evidence=[
            CapabilityEvidence(
                evidence_type="call",
                value="similarity_search(",
                file_path="src/tools.py",
                line=16,
            )
        ],
        side_effect=SideEffect.READ_ONLY,
        externality=Externality.LOCAL,
        reversibility=Reversibility.REVERSIBLE,
        trust_role=TrustRole.UNTRUSTED_INGRESS,
        rule_id="RULE-RET-SEARCH-001",
    )

    sink_cap = Capability(
        id="VCAP-01REFUND",
        name="process_refund [Financial Write]",
        source_symbol="process_refund",
        source_file="src/tools.py",
        source_line=30,
        tags=[CapabilityTag.FINANCIAL_WRITE, CapabilityTag.SIDE_EFFECT],
        confidence="high",
        evidence=[
            CapabilityEvidence(
                evidence_type="call",
                value="stripe.refund(",
                file_path="src/tools.py",
                line=32,
            )
        ],
        side_effect=SideEffect.MUTATING,
        externality=Externality.EXTERNAL,
        reversibility=Reversibility.IRREVERSIBLE,
        trust_role=TrustRole.PRIVILEGED_SINK,
        rule_id="RULE-FIN-REFUND-001",
    )

    graph = CapabilityGraph(
        nodes=[
            GraphNode(
                id="sym:search_knowledge_base", label="search_knowledge_base", node_type="tool"
            ),
            GraphNode(id="sym:process_refund", label="process_refund", node_type="tool"),
        ],
        edges=[
            GraphEdge(
                source="sym:search_knowledge_base",
                target="sym:process_refund",
                edge_type="possible_interaction",
                evidence="Agent workflow interacts with both tools",
            )
        ],
    )

    trust_boundaries = [
        TrustBoundary(
            id="VBOUND-0001",
            boundary_type="untrusted_ingress",
            source="external:untrusted",
            destination="agent:context",
            confidence="high",
            evidence=["search_knowledge_base"],
        ),
        TrustBoundary(
            id="VBOUND-0002",
            boundary_type="privileged_sink",
            source="agent:context",
            destination="process_refund",
            confidence="high",
            evidence=["process_refund"],
        ),
    ]

    analysis = CapabilityAnalysisResult(
        capabilities=[src_cap, sink_cap],
        trust_boundaries=trust_boundaries,
        graph=graph,
        statistics=CapabilityStatistics(total_capabilities=2),
    )

    # Invoke Phase 5 engine across the Phase 4 contract
    properties = infer_candidate_properties(analysis)

    assert len(properties) >= 1
    assert all(isinstance(p, Property) for p in properties)

    flow_prop = next(p for p in properties if isinstance(p.oracle, FlowForbiddenOracle))
    assert flow_prop.oracle.untrusted_source_key == "src/tools.py::search_knowledge_base"
    assert flow_prop.oracle.forbidden_sink_key == "src/tools.py::process_refund"
    assert flow_prop.applies_when.source_capability_keys == ["src/tools.py::search_knowledge_base"]
    assert flow_prop.applies_when.sink_capability_keys == ["src/tools.py::process_refund"]
