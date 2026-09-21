"""
Pydantic domain models for VIVEKA Phase 8 evaluation.

Represents evidence references (using RawEventType), evaluation results (preserving property_revision),
normalized execution traces (preserving ExecutionStatus), runtime capability bindings,
evaluation contexts, reproduction policies (enforcing minimum_violations <= runs),
reproduction runs, and aggregated reproduction results.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field, model_validator

from viveka.evaluation.vocabulary import EvaluationVerdict
from viveka.properties.models import Property
from viveka.runtime.models import RawEvent
from viveka.runtime.vocabulary import EventOrigin, ExecutionStatus, RawEventType
from viveka.worlds.models import World


class EvaluationEvidence(BaseModel):
    """Reference to an exact raw event in the trace supporting a verdict."""

    event_id: str = Field(description="Unique VEVT event identifier.")
    sequence: int = Field(ge=1, description="1-indexed event sequence number.")
    call_id: str | None = Field(default=None, description="Correlation UUID linking call/result.")
    event_type: RawEventType = Field(description="Preserved RawEventType enum.")
    event_origin: EventOrigin = Field(
        default=EventOrigin.VIVEKA_OBSERVED,
        description="Preserved EventOrigin (VIVEKA_OBSERVED or TARGET_REPORTED).",
    )
    description: str = Field(
        description="Human-readable explanation of why this event is evidence."
    )


class EvaluationResult(BaseModel):
    """Outcome of evaluating one execution trace against a property oracle."""

    eval_id: str = Field(description="Unique VEVAL-prefixed ULID identifier.")
    execution_id: str = Field(description="VRUN execution ID evaluated.")
    property_id: str = Field(description="VPROP property ID evaluated.")
    property_stable_key: str = Field(description="Stable key of property.")
    property_revision: int = Field(
        ge=1, description="Preserved revision number of property evaluated."
    )
    verdict: EvaluationVerdict = Field(description="Locked verdict outcome.")
    evidence: list[EvaluationEvidence] = Field(
        default_factory=list,
        description="Exact raw events referenced as evidence for this verdict.",
    )
    rationale: str = Field(default="", description="Detailed explanation of evaluation verdict.")
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExecutionTrace(BaseModel):
    """Structured, normalized execution trace derived from RuntimeResult."""

    trace_id: str = Field(description="Unique VTRC-prefixed ULID identifier.")
    execution_id: str = Field(description="VRUN execution identifier.")
    world_id: str = Field(description="VWORLD world identifier.")
    status: ExecutionStatus = Field(
        default=ExecutionStatus.SUCCESS,
        description="Preserved Phase 7 ExecutionStatus enum.",
    )
    events: list[RawEvent] = Field(default_factory=list, description="Ordered event stream.")
    calls_by_name: dict[str, list[RawEvent]] = Field(
        default_factory=dict, description="Tool name -> list of TOOL_CALL events."
    )
    results_by_call_id: dict[str, RawEvent] = Field(
        default_factory=dict, description="call_id -> TOOL_RESULT event mapping."
    )
    final_output: str = Field(default="", description="Final agent output text.")


class RuntimeCapabilityBinding(BaseModel):
    """Explicit mapping from Phase 5 stable capability keys to target runtime tool names.

    Evaluators MUST NEVER guess tool bindings by symbol-name similarity.
    """

    bindings: dict[str, str] = Field(
        default_factory=dict,
        description="Capability key '{path}::{symbol}' -> target tool name mapping.",
    )

    def resolve_tool(self, capability_key: str) -> str | None:
        """Return target runtime tool name for capability_key, or None if not mapped."""
        return self.bindings.get(capability_key)


class EvaluationContext(BaseModel):
    """Evaluation context bundling trace, target property, world, and capability binding."""

    trace: ExecutionTrace
    property: Property
    world: World | None = None
    binding: RuntimeCapabilityBinding


class ReproductionPolicy(BaseModel):
    """Configuration for N-of-M reproduction testing."""

    runs: int = Field(default=5, ge=1, description="Total trial runs to execute.")
    minimum_violations: int = Field(
        default=3, ge=1, description="Minimum violations required for reproduction."
    )

    @model_validator(mode="after")
    def validate_policy_bounds(self) -> ReproductionPolicy:
        if self.minimum_violations > self.runs:
            raise ValueError(
                f"minimum_violations ({self.minimum_violations}) cannot exceed total runs ({self.runs})."
            )
        return self


class ReproductionRun(BaseModel):
    """Detailed record of one trial run in a reproduction sequence."""

    run_index: int = Field(ge=0, description="0-indexed run number.")
    derived_seed: int = Field(description="SHA-256 derived seed for this run.")
    execution_id: str = Field(description="VRUN execution ID.")
    trace_id: str = Field(description="VTRC trace ID.")
    evaluation_id: str = Field(description="VEVAL evaluation ID.")
    verdict: EvaluationVerdict = Field(description="Verdict outcome of this run.")


class ReproductionResult(BaseModel):
    """Aggregated reproduction result over N trial runs."""

    property_id: str
    property_stable_key: str
    property_revision: int = Field(ge=1, description="Preserved revision number of property.")
    world_id: str
    master_seed: int = Field(description="Master random seed used for derivation.")
    seed_namespace: str = Field(description="Seed namespace string (e.g. world.id).")
    policy: ReproductionPolicy
    runs_detail: list[ReproductionRun] = Field(default_factory=list)
    total_runs: int
    violations_count: int
    no_violations_count: int
    inconclusive_count: int
    not_applicable_count: int
    criterion_met: bool = Field(
        description="True if violations_count >= policy.minimum_violations."
    )
    summary_message: str = Field(
        description="Human-readable summary, e.g. '4 / 5 runs violated the property (REPRODUCTION CRITERION MET)'."
    )
