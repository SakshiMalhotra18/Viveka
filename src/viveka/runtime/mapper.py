"""
Explicit lossless mapper from Phase 6 World to Phase 7 AgentRuntimeContext.

Verifies that all World fields are handled appropriately without silent dropping.
Raises UnsupportedWorldFeatureError if unhandleable feature configurations exist.
"""

from __future__ import annotations

from viveka.core.errors import VivekaError
from viveka.runtime.models import (
    AgentAuthorizationContext,
    AgentDocumentContext,
    AgentEnvironmentContext,
    AgentRuntimeContext,
    AgentStateContext,
    AgentToolConfigContext,
    AgentUserContext,
)
from viveka.worlds.models import World
from viveka.worlds.vocabulary import ToolBehavior


class UnsupportedWorldFeatureError(VivekaError):
    """Raised when a World contains features not supported by the runtime adapter."""


KNOWN_TOOL_BEHAVIORS: frozenset[str] = frozenset({b.value for b in ToolBehavior})


def map_world_to_context(world: World) -> AgentRuntimeContext:
    """Map a Phase 6 World to an AgentRuntimeContext losslessly.

    Raises UnsupportedWorldFeatureError if an unsupported feature configuration is found.
    """
    # 1. User slot
    user_ctx = AgentUserContext(
        user_id=world.user.id,
        role=world.user.role,
        permissions=list(world.user.permissions),
    )

    # 2. Retrieval slot
    doc_ctxs = [
        AgentDocumentContext(
            id=d.id,
            trust=d.trust.value if hasattr(d.trust, "value") else str(d.trust),
            content=d.content,
            metadata=dict(d.metadata),
        )
        for d in world.retrieval.documents
    ]

    # 3. Tools slot & validation
    tool_ctxs: dict[str, AgentToolConfigContext] = {}
    for tool_name, tool_cfg in world.tools.items():
        behavior_val = (
            tool_cfg.behavior.value
            if hasattr(tool_cfg.behavior, "value")
            else str(tool_cfg.behavior)
        )
        if behavior_val not in KNOWN_TOOL_BEHAVIORS:
            raise UnsupportedWorldFeatureError(
                f"Unsupported tool behavior '{behavior_val}' for tool '{tool_name}' in world {world.id}."
            )
        tool_ctxs[tool_name] = AgentToolConfigContext(
            behavior=behavior_val,
            response=tool_cfg.response,
            error_message=tool_cfg.error_message,
            latency_ms=tool_cfg.latency_ms,
        )

    # 4. Environment slot
    env_ctx = AgentEnvironmentContext(
        network_available=world.environment.network_available,
        latency_ms=world.environment.latency_ms,
        clock_offset_seconds=world.environment.clock_offset_seconds,
        available_configs=dict(world.environment.available_configs),
    )

    # 5. State slot
    conv_history = [
        {"role": turn.role, "content": turn.content} for turn in world.state.conversation_history
    ]
    state_ctx = AgentStateContext(
        conversation_history=conv_history,
        memory=dict(world.state.memory),
    )

    # 6. Authorization slot
    auth_ctx = AgentAuthorizationContext(
        user_permissions=list(world.authorization.user_permissions),
        approval_granted=world.authorization.approval_granted,
        approval_revoked=world.authorization.approval_revoked,
        spending_threshold=world.authorization.spending_threshold,
    )

    return AgentRuntimeContext(
        user=user_ctx,
        message=world.input.message,
        documents=doc_ctxs,
        tools=tool_ctxs,
        environment=env_ctx,
        state=state_ctx,
        authorization=auth_ctx,
    )
