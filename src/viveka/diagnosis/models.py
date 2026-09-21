"""
Pydantic domain models for VIVEKA Phase 10 diagnosis.

Diagnosis describes observable behavior only. Do not claim hidden reasoning,
proven root cause, or model/provider drift.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from viveka.runtime.vocabulary import EventOrigin, RawEventType


class DiagnosisEvidence(BaseModel):
    event_id: str = Field(description="Unique event identifier.")
    sequence: int = Field(ge=1, description="1-indexed event sequence number.")
    call_id: str | None = Field(default=None, description="Correlation UUID for TOOL_CALL/RESULT.")
    event_type: RawEventType = Field(description="Preserved RawEventType enum.")
    event_origin: EventOrigin = Field(
        default=EventOrigin.VIVEKA_OBSERVED,
        description="Preserved EventOrigin (VIVEKA_OBSERVED or TARGET_REPORTED).",
    )
    tool_name: str | None = Field(default=None, description="Tool name, if applicable.")
    description: str = Field(description="Observable description of why this event is relevant.")


class ContributingFactor(BaseModel):
    factor_type: str = Field(description="Structured factor type key.")
    label: str = Field(description="Short human-readable label.")
    description: str = Field(description="Observable description. No causal or root-cause claims.")
    evidence_event_ids: list[str] = Field(
        default_factory=list, description="Supporting evidence IDs."
    )


class TargetMetadata(BaseModel):
    adapter_type: str | None = Field(default=None)
    provider: str | None = Field(default=None)
    model: str | None = Field(default=None)
    model_revision: str | None = Field(default=None)
    temperature: float | None = Field(default=None, ge=0.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    top_k: int | None = Field(default=None, ge=0)
    max_tokens: int | None = Field(default=None, ge=1)
    git_commit: str | None = Field(default=None)
    system_prompt_hash: str | None = Field(default=None)
    extra: dict[str, Any] = Field(
        default_factory=dict, description="JSON-compatible extra metadata."
    )


class Diagnosis(BaseModel):
    diag_id: str = Field(description="Unique VDIAG-prefixed ULID identifier.")
    diagnosis_method: str = Field(default="deterministic_template_v1")
    reduction_id: str
    property_id: str
    property_stable_key: str
    property_revision: int = Field(ge=1)
    world_id: str
    original_world_id: str
    expected_behavior: str
    observed_behavior: str
    earliest_relevant_event: DiagnosisEvidence | None = None
    evidence: list[DiagnosisEvidence] = Field(default_factory=list)
    contributing_factors: list[ContributingFactor] = Field(default_factory=list)
    reproduction_summary: str
    limitations: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
