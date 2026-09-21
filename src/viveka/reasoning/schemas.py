"""
Structured output schemas for VIVEKA Phase 12 advisory reasoning.

All model output passes through these Pydantic models before entering
the VIVEKA domain. If output cannot be parsed or validated, advisory
generation fails and core verification remains unaffected.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from viveka.properties.vocabulary import InvariantType

# ---------------------------------------------------------------------------
# Property suggestion schemas
# ---------------------------------------------------------------------------


class PropertyProposal(BaseModel):
    """Model-generated property suggestion. Always enters the system as CANDIDATE."""

    name: str = Field(description="Short kebab-case property name slug.")
    description: str = Field(description="Clear human-readable statement of the invariant.")
    invariant_type: InvariantType = Field(description="Type of invariant.")
    source_capability_key: str = Field(
        description="Path-qualified capability key of the source (must exist in analysis)."
    )
    sink_capability_key: str | None = Field(
        default=None,
        description="Path-qualified capability key of the sink (must exist if present).",
    )
    allowed_exceptions: list[str] = Field(
        default_factory=list,
        description="Authorized override conditions.",
    )
    rationale: str = Field(description="Explanation of why this property should exist.")
    evidence_description: str = Field(
        description="Description of the evidence supporting this suggestion."
    )
    confidence: str = Field(
        default="low",
        description="Confidence level (always overridden to 'low' for model suggestions).",
    )


class PropertyProposalList(BaseModel):
    """Container for multiple property proposals from a single model call."""

    proposals: list[PropertyProposal] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# World suggestion schemas
# ---------------------------------------------------------------------------


class WorldDocumentProposal(BaseModel):
    """Model-generated document for a World suggestion."""

    trust: str = Field(description="Document trust level (must validate to DocumentTrust).")
    content: str = Field(description="Document text content.")


class ToolOverrideProposal(BaseModel):
    """Model-generated tool behavior override for a World suggestion."""

    behavior: str = Field(description="Tool behavior (must validate to ToolBehavior).")
    error_message: str | None = Field(
        default=None, description="Error message for exception/timeout behaviors."
    )


class WorldProposal(BaseModel):
    """Model-generated adversarial World suggestion."""

    scenario_description: str = Field(description="Human-readable scenario description.")
    input_message: str = Field(description="User input message for the World.")
    documents: list[WorldDocumentProposal] = Field(
        default_factory=list, description="Documents for retrieval context."
    )
    tool_overrides: dict[str, ToolOverrideProposal] = Field(
        default_factory=dict, description="Tool name → behavior override."
    )
    mutation_descriptions: list[str] = Field(
        default_factory=list, description="Human-readable mutation descriptions."
    )
    rationale: str = Field(description="Explanation of why this adversarial scenario is useful.")


class WorldProposalList(BaseModel):
    """Container for multiple world proposals from a single model call."""

    proposals: list[WorldProposal] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Diagnosis enrichment schemas
# ---------------------------------------------------------------------------


class AdvisoryDiagnosisNarrative(BaseModel):
    """Model-generated readable explanation of a deterministic Diagnosis.

    The deterministic Diagnosis remains the canonical analysis.
    This narrative is advisory and model-generated.
    """

    narrative: str = Field(description="Readable explanation of the diagnosis.")
    key_observations: list[str] = Field(
        default_factory=list, description="Key observable facts from the diagnosis."
    )
    possible_contributing_factors: list[str] = Field(
        default_factory=list, description="Possible contributing factors (not proven causes)."
    )
    recommended_investigation: list[str] = Field(
        default_factory=list, description="Suggested next steps for the developer."
    )
    disclaimer: str = Field(
        default=(
            "This narrative is advisory and model-generated. "
            "It does not establish internal reasoning, proven root cause, or causation. "
            "The deterministic diagnosis remains the canonical analysis."
        ),
        description="Mandatory disclaimer. Always present.",
    )


# ---------------------------------------------------------------------------
# Reasoning provenance
# ---------------------------------------------------------------------------


class ReasoningProvenance(BaseModel):
    """Metadata tracking which provider/model produced advisory output.

    Never stores API keys, bearer tokens, or authentication headers.
    Does not claim deterministic replay of advisory suggestions.
    """

    provider_kind: str = Field(description="Provider type: 'ollama', 'openai_compatible', 'fake'.")
    model: str = Field(description="Model name string.")
    endpoint_category: str = Field(description="'local' or 'remote'.")
    temperature: float | None = Field(default=None, description="Sampling temperature used.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="UTC timestamp."
    )
    viveka_version: str = Field(default="0.1.0", description="VIVEKA version at generation time.")
