"""
Tests for Phase 9 structural reduction operators and source World immutability.
"""

from __future__ import annotations

from viveka.reduction.operators import generate_reduction_candidates
from viveka.reduction.vocabulary import ReductionOperator
from viveka.worlds.models import (
    ConversationTurn,
    World,
    WorldDocument,
    WorldToolConfig,
)


def test_generate_reduction_candidates_structural() -> None:
    world = World(
        id="VWORLD-11111111111111111111111111",
        property_id="VPROP-11111111111111111111111111",
        property_stable_key="prop.flow",
        seed=42,
    )
    world.retrieval.documents.append(WorldDocument(id="doc-1", content="doc 1 content"))
    world.state.conversation_history.append(ConversationTurn(role="user", content="hello"))
    world.state.memory["user_tier"] = "gold"
    world.tools["refund.create"] = WorldToolConfig()
    world.user.permissions.append("refund.create")

    candidates = generate_reduction_candidates(world)

    operators_present = {c.operator for c in candidates}
    assert ReductionOperator.REMOVE_RETRIEVAL_DOCUMENT in operators_present
    assert ReductionOperator.REMOVE_CONVERSATION_TURN in operators_present
    assert ReductionOperator.REMOVE_MEMORY_ENTRY in operators_present
    assert ReductionOperator.REMOVE_TOOL_CONFIG in operators_present
    assert ReductionOperator.REMOVE_USER_PERMISSION in operators_present

    # Test Source World Immutability: original world is untouched
    assert len(world.retrieval.documents) == 1
    assert len(world.state.conversation_history) == 1
    assert "user_tier" in world.state.memory
    assert "refund.create" in world.tools
    assert "refund.create" in world.user.permissions
