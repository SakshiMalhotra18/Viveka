"""
Pydantic domain models for VIVEKA Phase 10 behavioral regression artifacts.

BehavioralRegression is the durable artifact preserving:
  - Full Property snapshot (approved at creation time)
  - Always-present final_world_snapshot (reduced or original World)
  - Exact stochastic replay contract (master_seed, seed_namespace, policy)
  - Compact RepresentativeEvidence snapshots (not just trace IDs)
  - Full Diagnosis snapshot (embedded for durability)
  - Target metadata (recorded only, not used for drift attribution)
  - Deterministic deduplication fingerprint

Privacy: artifacts are git-ignored by default.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from viveka.diagnosis.models import Diagnosis, TargetMetadata
from viveka.evaluation.models import (
    EvaluationEvidence,
    ReproductionPolicy,
    ReproductionResult,
)
from viveka.evaluation.vocabulary import EvaluationVerdict
from viveka.properties.models import Property
from viveka.worlds.models import World


class RepresentativeEvidence(BaseModel):
    """Compact snapshot of one run's evaluation evidence for durability.

    Preserves execution context without requiring EvaluationStore lookup.
    At least one VIOLATION representative must be stored when criterion_met is True.
    """

    execution_id: str = Field(description="VRUN execution ID.")
    trace_id: str = Field(description="VTRC trace ID.")
    evaluation_id: str = Field(description="VEVAL evaluation ID.")
    verdict: EvaluationVerdict = Field(description="Verdict outcome.")
    evidence: list[EvaluationEvidence] = Field(
        default_factory=list,
        description="Exact EvaluationEvidence references from this run.",
    )


class BehavioralRegression(BaseModel):
    """Durable behavioral regression artifact for future replay.

    Stores all context required to replay the stored World against the stored
    Property using the stored stochastic schedule.

    Privacy: artifacts may contain retrieved content, tool inputs/results, or PII.
    Review before sharing or committing.
    """

    regression_id: str = Field(description="Unique VREG-prefixed ULID identifier.")
    fingerprint: str = Field(description="SHA-256 regression deduplication fingerprint.")

    # Property snapshot (full model, approved at creation time)
    property_snapshot: Property = Field(description="Full approved Property snapshot.")
    property_stable_key: str = Field(description="Stable property key (cross-reference).")
    property_revision: int = Field(ge=1, description="Property revision at creation time.")

    # Always-present final world snapshot
    final_world_snapshot: World = Field(
        description="Final World model (reduced if reduction occurred, else original)."
    )
    final_world_fingerprint: str = Field(
        description="SHA-256 behavioral fingerprint of final_world_snapshot."
    )
    original_world_id: str = Field(description="ID of the original failing World.")
    original_world_fingerprint: str = Field(
        description="SHA-256 behavioral fingerprint of the original failing World."
    )

    # Provenance
    reduction_id: str = Field(description="VRED reduction ID.")
    diag_id: str | None = Field(default=None, description="VDIAG diagnosis ID cross-reference.")

    # Embedded Diagnosis snapshot for durability
    diagnosis_snapshot: Diagnosis | None = Field(
        default=None,
        description="Full Diagnosis snapshot embedded for durability.",
    )

    # Exact stochastic replay contract
    master_seed: int = Field(description="Master seed used for historical reproduction.")
    seed_namespace: str = Field(description="Seed namespace used for historical reproduction.")
    reproduction_policy: ReproductionPolicy = Field(description="Reproduction policy.")

    # Historical reproduction evidence
    historical_reproduction: ReproductionResult = Field(
        description="Reproduction result snapshot at regression creation time."
    )
    representative_evidence: list[RepresentativeEvidence] = Field(
        default_factory=list,
        description="Compact evidence snapshots: one VIOLATION (required), optionally one NO_OBSERVED_VIOLATION and one INCONCLUSIVE.",
    )

    # Optional target metadata (never used for drift attribution in Phase 10)
    target_metadata: TargetMetadata | None = Field(default=None)

    viveka_version: str = Field(description="VIVEKA package version at creation time.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReplayReport(BaseModel):
    """Factual result of replaying a stored BehavioralRegression.

    Reports raw K/N counts and category breakdowns.
    Does NOT say FIXED, REGRESSED, safer, or imply statistical significance.
    """

    regression_id: str
    property_stable_key: str
    property_revision: int

    # Historical K/N from stored regression
    historical_violations: int
    historical_no_observed_violations: int
    historical_inconclusive: int
    historical_not_applicable: int
    historical_runs: int
    historical_criterion_met: bool

    # Current K/N from live replay
    current_violations: int
    current_no_observed_violations: int
    current_inconclusive: int
    current_not_applicable: int
    current_runs: int
    current_criterion_met: bool

    # Property version mismatch (stored snapshot always used for replay)
    property_version_mismatch: bool = False
    property_mismatch_detail: str = ""

    # Factual observations - no FIXED/REGRESSED/statistical claims
    observations: list[str] = Field(
        default_factory=list,
        description="Factual observations comparing historical and current counts.",
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
