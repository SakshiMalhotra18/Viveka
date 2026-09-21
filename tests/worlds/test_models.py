"""Tests for Phase 6 World and Mutation Pydantic models."""

from viveka.core.ids import new_id
from viveka.worlds.models import (
    ConversationTurn,
    MutationRecord,
    World,
    WorldAuthorization,
    WorldDocument,
    WorldEnvironment,
    WorldInput,
    WorldRetrieval,
    WorldState,
    WorldToolConfig,
    WorldUser,
)
from viveka.worlds.vocabulary import (
    DocumentTrust,
    MutationFamily,
    MutationOperator,
    ToolBehavior,
    WorldSlotKind,
)


def test_world_defaults():
    world_id = new_id("VWORLD")
    w = World(
        id=world_id,
        property_id="VPROP-12345",
        property_stable_key="rule-01:forbidden_flow:src->sink",
        seed=42,
    )
    assert w.id == world_id
    assert w.seed == 42
    assert w.user.id == "user-1"
    assert w.input.message == ""
    assert w.retrieval.documents == []
    assert w.tools == {}
    assert w.environment.network_available is True
    assert w.authorization.approval_granted is True
    assert w.mutations == []


def test_world_serialization_roundtrip():
    w = World(
        id=new_id("VWORLD"),
        property_id="VPROP-9999",
        property_stable_key="test_key",
        seed=100,
        user=WorldUser(id="cust-1", role="customer"),
        input=WorldInput(message="Test input message"),
        retrieval=WorldRetrieval(
            documents=[
                WorldDocument(id="doc-1", trust=DocumentTrust.UNTRUSTED, content="Secrets inside")
            ]
        ),
        tools={
            "refund_order": WorldToolConfig(behavior=ToolBehavior.EXCEPTION, error_message="Failed")
        },
        environment=WorldEnvironment(network_available=False, latency_ms=100),
        state=WorldState(conversation_history=[ConversationTurn(role="user", content="Hello")]),
        authorization=WorldAuthorization(approval_granted=False),
        mutations=[
            MutationRecord(
                id=new_id("VMUT"),
                operator=MutationOperator.POISONED_DOCUMENT,
                family=MutationFamily.RETRIEVAL,
                target_slot=WorldSlotKind.RETRIEVAL,
                description="Added poison",
            )
        ],
    )

    dumped = w.model_dump(mode="json")
    reloaded = World.model_validate(dumped)

    assert reloaded.id == w.id
    assert reloaded.seed == 100
    assert reloaded.user.id == "cust-1"
    assert reloaded.retrieval.documents[0].content == "Secrets inside"
    assert reloaded.tools["refund_order"].behavior == ToolBehavior.EXCEPTION
    assert reloaded.environment.network_available is False
    assert len(reloaded.mutations) == 1
    assert reloaded.mutations[0].operator == MutationOperator.POISONED_DOCUMENT
