"""
Property suggestion advisor for VIVEKA Phase 12.

Uses an advisory ReasoningProvider to suggest candidate behavioral properties
grounded in Phase 4 capability evidence.

Model suggestions ALWAYS enter as CANDIDATE and require human review.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from viveka.core.ids import new_id
from viveka.properties.engine import generate_stable_key
from viveka.properties.models import (
    AppliesWhen,
    FailureHandledOracle,
    FlowForbiddenOracle,
    Property,
    PropertyEvidenceRef,
)
from viveka.properties.vocabulary import (
    InvariantType,
    PropertyEvidenceType,
    PropertySource,
    PropertyStatus,
)
from viveka.reasoning.budget import AdvisoryBudget
from viveka.reasoning.prompts import property_suggestion_prompt
from viveka.reasoning.schemas import PropertyProposal, PropertyProposalList

if TYPE_CHECKING:
    from viveka.capabilities.models import CapabilityAnalysisResult
    from viveka.properties.models import PropertyCatalog
    from viveka.reasoning.provider import ReasoningProvider


class PropertySuggestionResult(BaseModel):
    """Result of property suggestion enrichment."""

    suggested_candidates: list[Property] = Field(default_factory=list)
    rejected_proposals: list[dict[str, str]] = Field(default_factory=list)


class PropertySuggestionAdvisor:
    """Enriches candidate property discovery with advisory model suggestions."""

    def __init__(
        self,
        provider: ReasoningProvider,
        budget: AdvisoryBudget | None = None,
    ) -> None:
        self.provider = provider
        self.budget = budget or AdvisoryBudget()

    def suggest(
        self,
        analysis: CapabilityAnalysisResult,
        existing_catalog: PropertyCatalog | list[Property] | None = None,
    ) -> PropertySuggestionResult:
        """Generate candidate property suggestions from capability analysis.

        Args:
            analysis: Phase 4 capability analysis result.
            existing_catalog: Existing properties to avoid duplicating.

        Returns:
            PropertySuggestionResult with accepted candidates and rejected proposals.
        """
        self.budget.consume()

        # Build index of valid capability keys
        valid_cap_keys: set[str] = set()
        for cap in analysis.capabilities:
            valid_cap_keys.add(f"{cap.source_file}::{cap.source_symbol}")

        # Index existing stable keys
        existing_props: list[Property] = []
        if existing_catalog is not None:
            if hasattr(existing_catalog, "properties"):
                existing_props = existing_catalog.properties
            elif isinstance(existing_catalog, list):
                existing_props = existing_catalog
        existing_keys = {p.stable_key for p in existing_props}

        # Format capabilities and trust boundaries for prompt
        caps_data = [
            {
                "key": f"{c.source_file}::{c.source_symbol}",
                "symbol": c.source_symbol,
                "file": c.source_file,
                "line": c.source_line,
                "tags": [t.value for t in c.tags],
                "side_effect": c.side_effect.value,
                "trust_role": c.trust_role.value,
                "description": c.description,
            }
            for c in analysis.capabilities
        ]
        boundaries_data = [
            {
                "id": b.id,
                "type": b.boundary_type,
                "source": b.source,
                "destination": b.destination,
            }
            for b in analysis.trust_boundaries
        ]

        system_prompt, user_content = property_suggestion_prompt(
            capabilities_json=json.dumps(caps_data, indent=2),
            trust_boundaries_json=json.dumps(boundaries_data, indent=2),
            existing_stable_keys=sorted(existing_keys),
            response_schema=PropertyProposalList,
        )

        response: PropertyProposalList = self.provider.generate_structured(
            system_prompt=system_prompt,
            user_content=user_content,
            response_schema=PropertyProposalList,
        )

        suggested_candidates: list[Property] = []
        rejected_proposals: list[dict[str, str]] = []

        for p in response.proposals:
            rejection_reason = self._validate_proposal(p, valid_cap_keys, existing_keys)
            if rejection_reason:
                rejected_proposals.append({"proposal_name": p.name, "reason": rejection_reason})
                continue

            prop = self._convert_proposal_to_property(p)
            suggested_candidates.append(prop)
            existing_keys.add(prop.stable_key)

        return PropertySuggestionResult(
            suggested_candidates=suggested_candidates,
            rejected_proposals=rejected_proposals,
        )

    def _validate_proposal(
        self,
        p: PropertyProposal,
        valid_cap_keys: set[str],
        existing_keys: set[str],
    ) -> str | None:
        """Validate proposal references and check for duplicates."""
        if p.source_capability_key not in valid_cap_keys:
            return f"Source capability key '{p.source_capability_key}' does not exist in capability analysis."

        if p.invariant_type == InvariantType.FORBIDDEN_FLOW:
            if not p.sink_capability_key:
                return "Forbidden flow proposal must specify sink_capability_key."
            if p.sink_capability_key not in valid_cap_keys:
                return f"Sink capability key '{p.sink_capability_key}' does not exist in capability analysis."
            if p.source_capability_key == p.sink_capability_key:
                return "Source and sink capability keys cannot be identical."

        stable_key = generate_stable_key(
            rule_id="prop-rule-model-suggestion",
            invariant_type=p.invariant_type.value,
            source_cap_key=p.source_capability_key,
            sink_cap_key=p.sink_capability_key
            if p.invariant_type == InvariantType.FORBIDDEN_FLOW
            else None,
        )
        if stable_key in existing_keys:
            return f"Property with stable key '{stable_key}' already exists (duplicate suppressed)."

        return None

    def _convert_proposal_to_property(self, p: PropertyProposal) -> Property:
        """Convert a validated PropertyProposal into a typed Property domain model."""
        now = datetime.now(UTC)
        rule_id = "prop-rule-model-suggestion"

        if p.invariant_type == InvariantType.FORBIDDEN_FLOW:
            stable_key = generate_stable_key(
                rule_id=rule_id,
                invariant_type=p.invariant_type.value,
                source_cap_key=p.source_capability_key,
                sink_cap_key=p.sink_capability_key,
            )
            oracle = FlowForbiddenOracle(
                evaluator_kind="flow_forbidden",
                untrusted_source_key=p.source_capability_key,
                forbidden_sink_key=p.sink_capability_key or "",
                allowed_exceptions=list(p.allowed_exceptions),
            )
            applies = AppliesWhen(
                source_capability_keys=[p.source_capability_key],
                sink_capability_keys=[p.sink_capability_key] if p.sink_capability_key else [],
                source_symbols=[p.source_capability_key.split("::")[-1]],
                sink_symbols=[p.sink_capability_key.split("::")[-1]]
                if p.sink_capability_key
                else [],
            )
            evidence = [
                PropertyEvidenceRef(
                    evidence_type=PropertyEvidenceType.CAPABILITY,
                    source_id=p.source_capability_key,
                    description=f"Source capability: {p.source_capability_key}",
                    file_path=p.source_capability_key.split("::")[0],
                ),
                PropertyEvidenceRef(
                    evidence_type=PropertyEvidenceType.CAPABILITY,
                    source_id=p.sink_capability_key or "",
                    description=f"Sink capability: {p.sink_capability_key}",
                    file_path=(p.sink_capability_key or "").split("::")[0],
                ),
            ]
        else:
            stable_key = generate_stable_key(
                rule_id=rule_id,
                invariant_type=p.invariant_type.value,
                source_cap_key=p.source_capability_key,
            )
            oracle = FailureHandledOracle(
                evaluator_kind="failure_handled",
                target_action_key=p.source_capability_key,
                must_not_represent_action_as_successful=True,
            )
            applies = AppliesWhen(
                sink_capability_keys=[p.source_capability_key],
                sink_symbols=[p.source_capability_key.split("::")[-1]],
            )
            evidence = [
                PropertyEvidenceRef(
                    evidence_type=PropertyEvidenceType.CAPABILITY,
                    source_id=p.source_capability_key,
                    description=f"Target tool: {p.source_capability_key}",
                    file_path=p.source_capability_key.split("::")[0],
                )
            ]

        return Property(
            id=new_id("VPROP"),
            stable_key=stable_key,
            name=p.name,
            description=p.description,
            status=PropertyStatus.CANDIDATE,  # Always CANDIDATE, never approved
            source=PropertySource.MODEL_ASSISTED,
            confidence="low",  # Model suggestions always start at low confidence
            revision=1,
            applies_when=applies,
            oracle=oracle,
            evidence=evidence,
            rationale=p.rationale or f"Model-suggested invariant: {p.evidence_description}",
            rule_id=rule_id,
            created_at=now,
            updated_at=now,
        )
