"""
Boundary contract test for Phase 5 (PropertyCatalog / PropertyStore) -> Phase 6 (WorldGenerator).

Verifies that approved properties produced by the property engine can be directly
consumed by WorldGenerator to produce valid, serializable World objects.
"""

from viveka.capabilities.models import (
    Capability,
    CapabilityAnalysisResult,
    CapabilityGraph,
    GraphEdge,
    GraphNode,
    TrustBoundary,
)
from viveka.capabilities.vocabulary import CapabilityTag, SideEffect, TrustRole
from viveka.properties.engine import infer_candidate_properties
from viveka.properties.store import PropertyStore
from viveka.worlds.generate import WorldGenerator


def test_property_engine_to_world_generator_boundary(tmp_path):
    # 1. Produce synthetic Phase 4 CapabilityAnalysisResult
    src_cap = Capability(
        id="VCAP-01",
        name="retrieval_search",
        source_symbol="search_docs",
        source_file="src/search.py",
        source_line=10,
        tags=[CapabilityTag.RETRIEVAL, CapabilityTag.UNTRUSTED_INPUT],
        confidence="high",
        trust_role=TrustRole.UNTRUSTED_INGRESS,
    )
    sink_cap = Capability(
        id="VCAP-02",
        name="refund_create",
        source_symbol="refund_order",
        source_file="src/payment.py",
        source_line=25,
        tags=[CapabilityTag.FINANCIAL_WRITE],
        confidence="high",
        side_effect=SideEffect.MUTATING,
        trust_role=TrustRole.PRIVILEGED_SINK,
    )
    graph = CapabilityGraph(
        nodes=[
            GraphNode(id="sym:search_docs", label="search_docs", node_type="symbol"),
            GraphNode(id="sym:refund_order", label="refund_order", node_type="tool"),
        ],
        edges=[GraphEdge(source="sym:search_docs", target="sym:refund_order", edge_type="calls")],
    )
    trust_b = TrustBoundary(
        id="TB-01",
        boundary_type="untrusted_ingress",
        source="search_docs",
        destination="agent:context",
        confidence="high",
    )
    analysis = CapabilityAnalysisResult(
        capabilities=[src_cap, sink_cap],
        trust_boundaries=[trust_b],
        graph=graph,
    )

    # 2. Phase 5 Property Engine: infer candidates
    candidates = infer_candidate_properties(analysis)
    assert len(candidates) > 0

    # Save candidates to PropertyStore and approve one
    store = PropertyStore(tmp_path)
    store.merge_candidates(candidates)
    catalog = store.load_catalog()
    cand = catalog.candidates[0]
    approved_prop = store.approve(cand.id)

    # 3. Phase 6 World Generator: consume approved property catalog
    generator = WorldGenerator(seed=42)
    worlds = generator.generate_worlds([approved_prop], max_worlds_per_property=3)

    assert len(worlds) == 3
    for w in worlds:
        assert w.property_id == approved_prop.id
        assert w.property_stable_key == approved_prop.stable_key
        assert w.seed is not None
