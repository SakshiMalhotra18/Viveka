"""
Phase 8 -> 9 Boundary Test.

Verifies that real Phase 8 reproduction results integrate directly into the Phase 9
ReductionEngine without breaking contracts or altering Phase 8 internals.
"""

from __future__ import annotations

from viveka.evaluation.binding import get_demo_capability_binding
from viveka.evaluation.models import ReproductionPolicy
from viveka.properties.models import FlowForbiddenOracle, Property
from viveka.properties.vocabulary import PropertyStatus
from viveka.reduction.engine import ReductionEngine
from viveka.reduction.models import ReductionBudget
from viveka.worlds.models import ConversationTurn, World, WorldDocument


def test_phase8_to_phase9_boundary_reduction() -> None:
    prop = Property(
        id="VPROP-01JY8M7KFQZRVF2BNXD3TYA9WG",
        name="Flow Forbidden Boundary Test",
        description="Forbidden flow boundary test",
        oracle=FlowForbiddenOracle(
            untrusted_source_key="src.search::knowledge_search",
            forbidden_sink_key="src.payment::refund_order",
        ),
        status=PropertyStatus.APPROVED,
        stable_key="prop.flow_boundary",
    )

    world = World(
        id="VWORLD-01JY8M7KFQZRVF2BNXD3TYA9WG",
        property_id=prop.id,
        property_stable_key=prop.stable_key,
        seed=100,
    )
    # Add an extraneous document and a turn
    world.retrieval.documents.append(WorldDocument(id="doc-extra", content="extra irrelevant info"))
    world.state.conversation_history.append(ConversationTurn(role="user", content="hello agent"))
    world.authorization.approval_granted = False

    policy = ReproductionPolicy(runs=1, minimum_violations=1)
    budget = ReductionBudget(max_candidates=5, max_trials=20)
    binding = get_demo_capability_binding()

    engine = ReductionEngine()
    result = engine.reduce(
        property_obj=prop,
        world=world,
        policy=policy,
        budget=budget,
        binding=binding,
    )

    assert result.reduction_id.startswith("VRED-")
    assert result.baseline_reproduction.total_runs == 1
    assert result.baseline_trials == 1
    assert result.total_trials >= 1
