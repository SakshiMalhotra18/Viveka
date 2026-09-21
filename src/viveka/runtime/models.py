"""
Pydantic domain models for VIVEKA Phase 7 runtime execution.

Represents target specifications, typed sanitized runtime context losslessly mapped
from Phase 6 World definitions, execution requests, raw observable events with sequence
numbers and call correlation IDs, and runtime execution results.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from viveka.runtime.vocabulary import (
    EventOrigin,
    ExecutionStatus,
    RawEventType,
    RuntimeAdapterType,
)

# ---------------------------------------------------------------------------
# Target Specification
# ---------------------------------------------------------------------------


class TargetSpec(BaseModel):
    """Specification of how to load and invoke a target agent."""

    adapter_type: RuntimeAdapterType = Field(
        default=RuntimeAdapterType.PYTHON_CALLABLE,
        description="Adapter type to use for execution.",
    )
    import_path: str | None = Field(
        default=None,
        description="Python import path, e.g. 'viveka.demo.agent:run_demo_agent'.",
    )
    endpoint: str | None = Field(
        default=None,
        description="HTTP endpoint URL for HTTP targets, e.g. 'http://localhost:8000/agent'.",
    )
    working_directory: str = Field(default=".", description="Working directory for execution.")
    options: dict[str, str] = Field(
        default_factory=dict,
        description="Additional string options for adapter configuration.",
    )


# ---------------------------------------------------------------------------
# Typed Sanitized Runtime Context Sub-Models
# ---------------------------------------------------------------------------


class AgentUserContext(BaseModel):
    """User identity and permissions provided to the target."""

    user_id: str = Field(default="user-1", description="User ID.")
    role: str = Field(default="user", description="User role.")
    permissions: list[str] = Field(default_factory=list, description="Granted permissions.")


class AgentDocumentContext(BaseModel):
    """Retrieval document provided to the target."""

    id: str = Field(description="Document ID.")
    trust: str = Field(default="untrusted", description="Trust level ('trusted', 'untrusted').")
    content: str = Field(default="", description="Document text content.")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata key-values.")


class AgentToolConfigContext(BaseModel):
    """Tool behavior override provided to the runtime tool wrappers."""

    behavior: str = Field(default="normal", description="Tool behavior override name.")
    response: str | None = Field(default=None, description="Custom response content.")
    error_message: str | None = Field(default=None, description="Simulated error message.")
    latency_ms: int | None = Field(default=None, ge=0, description="Simulated latency in ms.")


class AgentEnvironmentContext(BaseModel):
    """Environmental state provided to the target."""

    network_available: bool = Field(default=True, description="Whether network is reachable.")
    latency_ms: int = Field(default=0, ge=0, description="Simulated network latency.")
    clock_offset_seconds: int = Field(default=0, description="Simulated clock offset.")
    available_configs: dict[str, str] = Field(
        default_factory=dict, description="Available configs."
    )


class AgentStateContext(BaseModel):
    """Pre-existing conversation and memory state provided to the target."""

    conversation_history: list[dict[str, str]] = Field(
        default_factory=list, description="List of turn dicts ({'role': ..., 'content': ...})."
    )
    memory: dict[str, str] = Field(default_factory=dict, description="Key-value memory state.")


class AgentAuthorizationContext(BaseModel):
    """Authorization context provided to the target."""

    user_permissions: list[str] = Field(default_factory=list, description="User permissions.")
    approval_granted: bool = Field(default=True, description="Approval granted flag.")
    approval_revoked: bool = Field(default=False, description="Approval revoked flag.")
    spending_threshold: float | None = Field(
        default=None, ge=0, description="Spending threshold limit."
    )


class AgentRuntimeContext(BaseModel):
    """Sanitized, typed runtime context passed to the target agent.

    Derived losslessly from Phase 6 World.
    Contains NO properties, oracles, expected failures, or VIVEKA secrets.
    """

    user: AgentUserContext = Field(default_factory=AgentUserContext)
    message: str = Field(default="", description="User input message.")
    documents: list[AgentDocumentContext] = Field(
        default_factory=list, description="Retrieval documents."
    )
    tools: dict[str, AgentToolConfigContext] = Field(
        default_factory=dict, description="Tool behavior overrides."
    )
    environment: AgentEnvironmentContext = Field(default_factory=AgentEnvironmentContext)
    state: AgentStateContext = Field(default_factory=AgentStateContext)
    authorization: AgentAuthorizationContext = Field(default_factory=AgentAuthorizationContext)


# ---------------------------------------------------------------------------
# Execution Request
# ---------------------------------------------------------------------------


class RuntimeRequest(BaseModel):
    """Execution request for one target run."""

    execution_id: str = Field(description="Unique VRUN-prefixed ULID identifier.")
    world_id: str = Field(description="Phase 6 World ID being executed.")
    target: TargetSpec = Field(description="Specification of target agent.")
    context: AgentRuntimeContext = Field(
        description="Sanitized runtime context derived from World."
    )
    seed: int = Field(default=12345, description="Random seed for reproducible execution.")
    timeout_seconds: float = Field(
        default=30.0, gt=0, description="Enforceable execution timeout in seconds."
    )


# ---------------------------------------------------------------------------
# Raw Observable Event & Execution Result
# ---------------------------------------------------------------------------


class RawEvent(BaseModel):
    """A single raw observable runtime event.

    Features a 1-indexed monotonically increasing sequence number and optional
    call_id correlation UUID for pairing TOOL_CALL and TOOL_RESULT events.
    """

    sequence: int = Field(ge=1, description="1-indexed monotonically increasing event sequence.")
    event_id: str = Field(description="Unique identifier for this event.")
    event_type: RawEventType = Field(description="Category of raw event.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp of event creation.",
    )
    call_id: str | None = Field(
        default=None,
        description="Correlation ID (UUID) linking TOOL_CALL and TOOL_RESULT pairs.",
    )
    tool_name: str | None = Field(default=None, description="Name of tool called, if applicable.")
    tool_args: dict[str, Any] | None = Field(
        default=None, description="Tool invocation arguments, if applicable."
    )
    tool_result: Any | None = Field(
        default=None, description="Tool invocation return value or error."
    )
    error_message: str | None = Field(
        default=None, description="Error message, if event_type is error."
    )
    output_text: str | None = Field(
        default=None, description="Agent text output chunk, if applicable."
    )
    origin: EventOrigin = Field(
        default=EventOrigin.VIVEKA_OBSERVED,
        description="Provenance origin of the event (VIVEKA_OBSERVED or TARGET_REPORTED).",
    )


class RuntimeResult(BaseModel):
    """Outcome of executing a target run."""

    execution_id: str = Field(description="Unique VRUN execution identifier.")
    world_id: str = Field(description="Phase 6 World ID executed.")
    status: ExecutionStatus = Field(description="Outcome status of execution.")
    events: list[RawEvent] = Field(
        default_factory=list, description="Ordered sequence of raw observable events."
    )
    final_output: str = Field(default="", description="Final text output produced by agent.")
    error_message: str | None = Field(default=None, description="Error message if run failed.")
    execution_time_ms: float = Field(default=0.0, ge=0.0, description="Total execution time in ms.")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when result was created.",
    )
