"""
Pydantic domain models for VIVEKA Phase 5 properties.

Represents behavioral properties, invariants, applicability conditions,
typed oracle specifications, evidence references, and property catalogs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from viveka.properties.vocabulary import (
    PropertyEvidenceType,
    PropertySource,
    PropertyStatus,
)


class FlowForbiddenOracle(BaseModel):
    """Oracle specification for forbidden flow invariants."""

    evaluator_kind: Literal["flow_forbidden"] = "flow_forbidden"
    untrusted_source_key: str = Field(
        description="Path-qualified stable capability key of the untrusted ingress source."
    )
    forbidden_sink_key: str = Field(
        description="Path-qualified stable capability key of the forbidden sink action."
    )
    allowed_exceptions: list[str] = Field(
        default_factory=list,
        description="Authorized override conditions (e.g. 'explicit_user_authorization').",
    )


class FailureHandledOracle(BaseModel):
    """Oracle specification for tool failure handling invariants."""

    evaluator_kind: Literal["failure_handled"] = "failure_handled"
    target_action_key: str = Field(
        description="Path-qualified stable capability key of the exposed tool."
    )
    must_not_represent_action_as_successful: bool = Field(
        default=True,
        description="Semantic invariant: if tool execution fails, agent must not claim success.",
    )


PropertyOracle = Annotated[
    FlowForbiddenOracle | FailureHandledOracle,
    Field(discriminator="evaluator_kind"),
]


class PropertyEvidenceRef(BaseModel):
    """A concrete piece of structural or capability evidence supporting a property."""

    evidence_type: PropertyEvidenceType = Field(description="Category of supporting evidence.")
    source_id: str = Field(
        description="Stable capability key, boundary ID, or graph path description."
    )
    description: str = Field(
        description="Human-readable description of why this supports the property."
    )
    file_path: str = Field(description="Project-relative file path.")
    line: int | None = Field(
        default=None,
        ge=1,
        description="Line number if evidence maps to a specific source line, or None.",
    )


class PropertyRevisionRecord(BaseModel):
    """Immutable audit record of a property state transition or update."""

    revision: int = Field(ge=1, description="Sequential revision number.")
    status: PropertyStatus = Field(description="Property status at this revision.")
    timestamp: datetime = Field(description="Timezone-aware UTC timestamp when revision occurred.")
    reason: str = Field(default="", description="Reason for revision.")
    actor: str = Field(default="developer", description="Actor who made the change.")


class AppliesWhen(BaseModel):
    """Scope conditions bound to stable capability keys."""

    source_capability_keys: list[str] = Field(
        default_factory=list,
        description="Stable capability keys ({path}::{symbol}) of ingress sources.",
    )
    sink_capability_keys: list[str] = Field(
        default_factory=list,
        description="Stable capability keys ({path}::{symbol}) of sink actions.",
    )
    source_symbols: list[str] = Field(
        default_factory=list,
        description="Qualified symbol names of ingress sources.",
    )
    sink_symbols: list[str] = Field(
        default_factory=list,
        description="Qualified symbol names of sink actions.",
    )


class Property(BaseModel):
    """A behavioral property in VIVEKA.

    Represents an invariant that should always remain true about an agent.
    Properties start as 'candidate' and become active verification baselines
    only after explicit human approval.
    """

    id: str = Field(description="Unique identifier with VPROP prefix (e.g. 'VPROP-01...').")
    stable_key: str = Field(
        description="Deterministic content hash for deduplication across inspection runs."
    )
    name: str = Field(
        description="Short human-readable property slug (e.g. 'retrieved-content-cannot-authorize-refund')."
    )
    description: str = Field(description="Clear human-readable statement of the invariant.")
    status: PropertyStatus = Field(
        default=PropertyStatus.CANDIDATE,
        description="Lifecycle status ('candidate', 'approved', 'rejected', 'disabled', 'deprecated').",
    )
    source: PropertySource = Field(
        default=PropertySource.RULE_DERIVED,
        description="Origin source of this property.",
    )
    confidence: str = Field(
        default="medium",
        description="Confidence level in the suggestion ('high', 'medium', 'low').",
    )
    revision: int = Field(
        default=1,
        ge=1,
        description="Monotonically increasing revision number.",
    )
    revision_history: list[PropertyRevisionRecord] = Field(
        default_factory=list,
        description="Audit log of state transitions.",
    )
    applies_when: AppliesWhen = Field(
        default_factory=AppliesWhen,
        description="Application conditions bound to stable capability keys.",
    )
    oracle: PropertyOracle = Field(
        description="Typed evaluation oracle specification.",
    )
    evidence: list[PropertyEvidenceRef] = Field(
        default_factory=list,
        description="Typed evidence references supporting this property.",
    )
    rationale: str = Field(
        default="",
        description="Explanation of why this property was proposed.",
    )
    rule_id: str | None = Field(
        default=None,
        description="Identifier of the rule that generated this property, if applicable.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when the property was created.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="UTC timestamp when the property was last updated.",
    )


class PropertyCatalog(BaseModel):
    """Collection of properties loaded for a project."""

    properties: list[Property] = Field(default_factory=list)

    @property
    def approved(self) -> list[Property]:
        return [p for p in self.properties if p.status == PropertyStatus.APPROVED]

    @property
    def candidates(self) -> list[Property]:
        return [p for p in self.properties if p.status == PropertyStatus.CANDIDATE]

    @property
    def rejected(self) -> list[Property]:
        return [p for p in self.properties if p.status == PropertyStatus.REJECTED]

    def by_id(self, prop_id: str) -> Property | None:
        for p in self.properties:
            if p.id == prop_id:
                return p
        return None

    def by_stable_key(self, stable_key: str) -> Property | None:
        for p in self.properties:
            if p.stable_key == stable_key:
                return p
        return None
