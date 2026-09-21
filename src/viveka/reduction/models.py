"""
Pydantic domain models for VIVEKA Phase 9 reproducible failure reduction engine.

Defines reduction budgets, candidate simplifications, step audit records,
and the complete expanded ReductionResult domain object.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from viveka.evaluation.models import ReproductionPolicy, ReproductionResult
from viveka.reduction.vocabulary import ReductionOperator, ReductionStopReason
from viveka.worlds.models import World


class ReductionBudget(BaseModel):
    """Execution budget for failure reduction search."""

    max_candidates: int = Field(
        default=10,
        ge=1,
        description="Maximum candidate worlds to test.",
    )
    max_trials: int = Field(
        default=50,
        ge=1,
        description="Maximum total trial runs across baseline and candidate testing.",
    )


class ReductionCandidate(BaseModel):
    """A proposed structural simplification of a World."""

    candidate_id: str = Field(description="Candidate identifier (e.g. CAND-1).")
    parent_world_id: str = Field(description="ID of the parent world being simplified.")
    operator: ReductionOperator = Field(description="Structural reduction operator applied.")
    target_item_key: str = Field(description="Description/key of the removed structural element.")
    world: World = Field(description="The simplified candidate World.")


class ReductionStep(BaseModel):
    """Record of a single tested reduction attempt (accepted or rejected)."""

    step_index: int = Field(ge=1, description="1-indexed sequence of trial attempt.")
    candidate_id: str = Field(description="Candidate identifier.")
    parent_world_id: str = Field(description="Parent world ID.")
    candidate_world_id: str = Field(description="Candidate world ID.")
    operator: ReductionOperator = Field(description="Operator applied.")
    target_item_key: str = Field(description="Target item description.")
    reproduction_result: ReproductionResult = Field(
        description="Complete reproduction result for this candidate.",
    )
    accepted: bool = Field(
        description="True if candidate met the reproduction criterion and was accepted.",
    )


class ReductionResult(BaseModel):
    """Full domain object recording a reproducible failure reduction session."""

    reduction_id: str = Field(description="Unique VRED-prefixed ULID identifier.")
    property_id: str = Field(description="Target property ID.")
    property_stable_key: str = Field(description="Stable key of target property.")
    property_revision: int = Field(description="Revision number of target property.")
    original_world_id: str = Field(description="ID of the original failing baseline world.")
    reduced_world_id: str | None = Field(
        default=None,
        description="ID of final reduced world if any reduction occurred, or None.",
    )
    reduced_world: World | None = Field(
        default=None,
        description="Final reduced World model if reduction occurred, or None.",
    )
    stop_reason: ReductionStopReason = Field(description="Factual stop reason.")
    policy: ReproductionPolicy = Field(description="Locked reproduction policy used.")
    budget: ReductionBudget = Field(description="Configured reduction search budget.")
    master_seed: int = Field(description="Master seed used for derivation.")
    seed_namespace: str = Field(description="Shared seed namespace used across all runs.")
    baseline_reproduction: ReproductionResult = Field(
        description="Baseline world reproduction result.",
    )
    final_reproduction: ReproductionResult = Field(
        description="Reproduction result of the final world (baseline or last accepted candidate).",
    )
    steps: list[ReductionStep] = Field(
        default_factory=list,
        description="Complete list of tested reduction attempts (accepted and rejected) in order.",
    )
    baseline_trials: int = Field(ge=0, description="Trial runs executed for baseline world.")
    candidate_trials: int = Field(ge=0, description="Trial runs executed across candidate testing.")
    total_trials: int = Field(ge=0, description="Total trial runs executed (baseline + candidate).")
    summary_message: str = Field(description="Human-readable outcome summary.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
