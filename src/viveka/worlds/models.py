"""
Pydantic domain models for VIVEKA Phase 6 worlds.

Represents the complete environment for one trial: user identity, input message,
retrieval documents, tool behavior overrides, environmental conditions,
conversation state, authorization, and applied mutations.

All models are serializable to YAML for reproducibility (§42).
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from viveka.worlds.vocabulary import (
    DocumentTrust,
    MutationFamily,
    MutationOperator,
    ToolBehavior,
    WorldSlotKind,
)

# ---------------------------------------------------------------------------
# World slot models (§16)
# ---------------------------------------------------------------------------


class WorldUser(BaseModel):
    """Identity and role of the simulated user in a world."""

    id: str = Field(description="User identifier (e.g. 'customer-42').")
    role: str = Field(default="user", description="User role (e.g. 'customer', 'admin').")
    permissions: list[str] = Field(
        default_factory=list,
        description="Permissions granted to this user.",
    )


class WorldInput(BaseModel):
    """The user's input message for this world."""

    message: str = Field(default="", description="User message text.")


class WorldDocument(BaseModel):
    """A document available to the agent via retrieval."""

    id: str = Field(description="Document identifier (e.g. 'doc-1').")
    trust: DocumentTrust = Field(
        default=DocumentTrust.UNTRUSTED,
        description="Trust level of this document.",
    )
    content: str = Field(default="", description="Document text content.")
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Optional metadata key-value pairs.",
    )


class WorldRetrieval(BaseModel):
    """Retrieval context: documents available to the agent."""

    documents: list[WorldDocument] = Field(default_factory=list)


class WorldToolConfig(BaseModel):
    """Behavior override for a specific tool in this world."""

    behavior: ToolBehavior = Field(
        default=ToolBehavior.NORMAL,
        description="How the tool behaves (normal, timeout, exception, etc.).",
    )
    response: str | None = Field(
        default=None,
        description="Custom response content if overridden.",
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if behavior is exception/timeout.",
    )
    latency_ms: int | None = Field(
        default=None,
        ge=0,
        description="Simulated latency in milliseconds.",
    )


class ConversationTurn(BaseModel):
    """A single turn in conversation history."""

    role: str = Field(description="Turn role: 'user', 'assistant', or 'system'.")
    content: str = Field(description="Turn content text.")


class WorldState(BaseModel):
    """Pre-existing conversation/memory state for the world."""

    conversation_history: list[ConversationTurn] = Field(default_factory=list)
    memory: dict[str, str] = Field(
        default_factory=dict,
        description="Key-value memory entries available to the agent.",
    )


class WorldEnvironment(BaseModel):
    """Environmental conditions for the world."""

    network_available: bool = Field(default=True, description="Whether network is reachable.")
    latency_ms: int = Field(default=0, ge=0, description="Simulated network latency.")
    clock_offset_seconds: int = Field(
        default=0,
        description="Clock offset from real time in seconds.",
    )
    available_configs: dict[str, str] = Field(
        default_factory=dict,
        description="Configuration values available to the agent.",
    )


class WorldAuthorization(BaseModel):
    """Authorization state for the world."""

    user_permissions: list[str] = Field(
        default_factory=list,
        description="Permissions granted to the user.",
    )
    approval_granted: bool = Field(
        default=True,
        description="Whether a required approval is currently granted.",
    )
    approval_revoked: bool = Field(
        default=False,
        description="Whether a previously granted approval has been revoked.",
    )
    spending_threshold: float | None = Field(
        default=None,
        ge=0,
        description="Maximum allowed spending/action threshold.",
    )


# ---------------------------------------------------------------------------
# Mutation record
# ---------------------------------------------------------------------------


class MutationRecord(BaseModel):
    """A single applied mutation with its operator, family, and parameters."""

    id: str = Field(description="Unique VMUT-prefixed ULID identifier.")
    operator: MutationOperator = Field(description="The mutation operator applied.")
    family: MutationFamily = Field(description="The mutation family this operator belongs to.")
    target_slot: WorldSlotKind = Field(description="Which world slot was mutated.")
    description: str = Field(description="Human-readable description of the mutation.")
    parameters: dict[str, str] = Field(
        default_factory=dict,
        description="Operator-specific parameters used during mutation.",
    )


# ---------------------------------------------------------------------------
# World (top-level)
# ---------------------------------------------------------------------------


class World(BaseModel):
    """A complete world definition — the test environment for one trial.

    Worlds are reproducible: a seed + property + mutation list
    deterministically produces the same world (§42).
    """

    id: str = Field(description="Unique VWORLD-prefixed ULID identifier.")
    property_id: str = Field(description="The approved property this world targets.")
    property_stable_key: str = Field(
        description="Stable key of the property, for persistence across ID changes.",
    )
    seed: int = Field(description="Random seed used for reproducibility.")

    # Typed slots (§16)
    user: WorldUser = Field(default_factory=lambda: WorldUser(id="user-1"))
    input: WorldInput = Field(default_factory=WorldInput)
    retrieval: WorldRetrieval = Field(default_factory=WorldRetrieval)
    tools: dict[str, WorldToolConfig] = Field(
        default_factory=dict,
        description="Tool name → behavior override mapping.",
    )
    environment: WorldEnvironment = Field(default_factory=WorldEnvironment)
    state: WorldState = Field(default_factory=WorldState)
    authorization: WorldAuthorization = Field(default_factory=WorldAuthorization)

    # Applied mutations
    mutations: list[MutationRecord] = Field(
        default_factory=list,
        description="Ordered list of mutations applied to produce this world.",
    )

    # Metadata
    origin: str = Field(
        default="deterministic",
        description="Origin of this World: 'deterministic' or 'model_assisted'.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when this world was generated.",
    )
