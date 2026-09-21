"""
Diagnosis narrative enricher for VIVEKA Phase 12.

Produces a human-readable advisory narrative explaining a deterministic
Phase 10 Diagnosis.

The deterministic Diagnosis remains canonical. The narrative is advisory only
and never claims internal reasoning, intent, or unproven causation.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from viveka.reasoning.budget import AdvisoryBudget
from viveka.reasoning.prompts import diagnosis_enrichment_prompt
from viveka.reasoning.schemas import AdvisoryDiagnosisNarrative, ReasoningProvenance

if TYPE_CHECKING:
    from viveka.diagnosis.models import Diagnosis
    from viveka.properties.models import Property
    from viveka.reasoning.provider import ReasoningProvider


class DiagnosisEnricher:
    """Enriches a deterministic Diagnosis with an advisory human-readable narrative."""

    def __init__(
        self,
        provider: ReasoningProvider,
        budget: AdvisoryBudget | None = None,
    ) -> None:
        self.provider = provider
        self.budget = budget or AdvisoryBudget()

    def enrich(
        self,
        diagnosis: Diagnosis,
        property_obj: Property | str | None = None,
    ) -> tuple[AdvisoryDiagnosisNarrative, ReasoningProvenance]:
        """Produce an advisory narrative from a deterministic Diagnosis.

        Args:
            diagnosis: The canonical Phase 10 Diagnosis artifact.
            property_obj: Property instance or description string for context.

        Returns:
            Tuple of (AdvisoryDiagnosisNarrative, ReasoningProvenance).
        """
        self.budget.consume()

        prop_desc = ""
        if isinstance(property_obj, str):
            prop_desc = property_obj
        elif property_obj is not None:
            prop_desc = f"Property '{property_obj.name}': {property_obj.description}"
        else:
            prop_desc = f"Property stable key: {diagnosis.property_stable_key}"

        diag_data = {
            "diag_id": diagnosis.diag_id,
            "expected_behavior": diagnosis.expected_behavior,
            "observed_behavior": diagnosis.observed_behavior,
            "evidence": [
                {
                    "event_id": e.event_id,
                    "sequence": e.sequence,
                    "event_type": e.event_type.value
                    if hasattr(e.event_type, "value")
                    else str(e.event_type),
                    "tool_name": e.tool_name,
                    "description": e.description,
                }
                for e in diagnosis.evidence
            ],
            "contributing_factors": [
                {
                    "factor_type": f.factor_type,
                    "label": f.label,
                    "description": f.description,
                }
                for f in diagnosis.contributing_factors
            ],
            "limitations": diagnosis.limitations,
        }

        system_prompt, user_content = diagnosis_enrichment_prompt(
            diagnosis_json=json.dumps(diag_data, indent=2),
            property_description=prop_desc,
            response_schema=AdvisoryDiagnosisNarrative,
        )

        narrative: AdvisoryDiagnosisNarrative = self.provider.generate_structured(
            system_prompt=system_prompt,
            user_content=user_content,
            response_schema=AdvisoryDiagnosisNarrative,
        )

        provenance = ReasoningProvenance(
            provider_kind=self.provider.provider_kind,
            model=self.provider.model_name,
            endpoint_category=self.provider.endpoint_category,
        )

        return narrative, provenance
