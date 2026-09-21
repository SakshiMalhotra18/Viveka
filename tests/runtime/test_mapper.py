"""Tests for Phase 6 World to Phase 7 AgentRuntimeContext mapping."""

import pytest

from viveka.core.ids import new_id
from viveka.runtime.mapper import UnsupportedWorldFeatureError, map_world_to_context
from viveka.worlds.models import (
    ConversationTurn,
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
from viveka.worlds.vocabulary import DocumentTrust, ToolBehavior


def test_map_world_to_context_lossless():
    w = World(
        id=new_id("VWORLD"),
        property_id="VPROP-01",
        property_stable_key="test_key",
        seed=42,
        user=WorldUser(id="user-42", role="customer", permissions=["read"]),
        input=WorldInput(message="Process refund"),
        retrieval=WorldRetrieval(
            documents=[
                WorldDocument(id="doc-1", trust=DocumentTrust.UNTRUSTED, content="Secret text")
            ]
        ),
        tools={"refund.create": WorldToolConfig(behavior=ToolBehavior.NORMAL, latency_ms=50)},
        environment=WorldEnvironment(network_available=True, latency_ms=10),
        state=WorldState(
            conversation_history=[ConversationTurn(role="user", content="Hi")],
            memory={"session_id": "abc"},
        ),
        authorization=WorldAuthorization(approval_granted=True, spending_threshold=100.0),
    )

    ctx = map_world_to_context(w)

    assert ctx.user.user_id == "user-42"
    assert ctx.user.permissions == ["read"]
    assert ctx.message == "Process refund"
    assert len(ctx.documents) == 1
    assert ctx.documents[0].content == "Secret text"
    assert ctx.tools["refund.create"].behavior == "normal"
    assert ctx.environment.network_available is True
    assert ctx.state.conversation_history == [{"role": "user", "content": "Hi"}]
    assert ctx.state.memory == {"session_id": "abc"}
    assert ctx.authorization.approval_granted is True
    assert ctx.authorization.spending_threshold == 100.0


def test_map_world_to_context_unsupported_feature():
    unsupported_cfg = WorldToolConfig.model_construct(behavior="custom_unknown_behavior")
    w = World(
        id=new_id("VWORLD"),
        property_id="VPROP-01",
        property_stable_key="test_key",
        seed=42,
        tools={"bad_tool": unsupported_cfg},
    )

    with pytest.raises(UnsupportedWorldFeatureError, match="Unsupported tool behavior"):
        map_world_to_context(w)
