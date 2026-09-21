"""
Pydantic domain models for VIVEKA Phase 11 verification results.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from viveka.diagnosis.models import Diagnosis
from viveka.evaluation.models import ReproductionResult
from viveka.reduction.models import ReductionResult
from viveka.regression.models import BehavioralRegression
from viveka.verification.vocabulary import PropertyVerificationStatus, VerificationOutcome


class WorldVerificationDetail(BaseModel):
    """Result of verifying a single World against a Property."""

    world_id: str
    reproduction: ReproductionResult | None = None
    reduction: ReductionResult | None = None
    diagnosis: Diagnosis | None = None
    regression: BehavioralRegression | None = None
    error_message: str | None = None


class PropertyVerificationResult(BaseModel):
    """Verification outcome for one approved Property."""

    property_id: str
    property_name: str
    property_stable_key: str
    property_revision: int
    status: PropertyVerificationStatus
    worlds_tested: int = 0
    worlds_violated: int = 0
    world_details: list[WorldVerificationDetail] = Field(default_factory=list)
    reduction_id: str | None = None
    diag_id: str | None = None
    regression_id: str | None = None
    error_message: str | None = None
    advisory_narrative: str | None = None


class VerificationResult(BaseModel):
    """Top-level result of a `viveka verify` run."""

    schema_version: int = 1
    outcome: VerificationOutcome
    target_command: str | None = None
    properties_considered: int = 0
    properties_verified: int = 0
    properties_passed: int = 0
    properties_violated: int = 0
    properties_errored: int = 0
    total_worlds_tested: int = 0
    regressions_created: int = 0
    candidate_properties_count: int = 0
    property_results: list[PropertyVerificationResult] = Field(default_factory=list)
    summary_message: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
