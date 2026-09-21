"""
World suggestion advisor for VIVEKA Phase 12.

Uses an advisory ReasoningProvider to suggest adversarial test scenarios (Worlds)
targeting an approved Property.

Model-generated Worlds undergo the exact same deterministic runtime and
evaluation pipeline as deterministically generated Worlds.
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from viveka.core.ids import new_id
from viveka.reasoning.budget import AdvisoryBudget
from viveka.reasoning.prompts import world_suggestion_prompt
from viveka.reasoning.schemas import WorldProposal, WorldProposalList
from viveka.worlds.models import (
    World,
    WorldDocument,
    WorldInput,
    WorldRetrieval,
    WorldToolConfig,
)
from viveka.worlds.vocabulary import DocumentTrust, ToolBehavior

if TYPE_CHECKING:
    from viveka.evaluation.models import RuntimeCapabilityBinding
    from viveka.properties.models import Property
    from viveka.reasoning.provider import ReasoningProvider


class WorldSuggestionResult(BaseModel):
    """Result of world suggestion enrichment."""

    suggested_worlds: list[World] = Field(default_factory=list)
    rejected_proposals: list[dict[str, str]] = Field(default_factory=list)


class WorldSuggestionAdvisor:
    """Enriches adversarial world generation with advisory model suggestions."""

    def __init__(
        self,
        provider: ReasoningProvider,
        budget: AdvisoryBudget | None = None,
    ) -> None:
        self.provider = provider
        self.budget = budget or AdvisoryBudget()

    def suggest(
        self,
        property_obj: Property,
        available_tools: list[str] | RuntimeCapabilityBinding | None = None,
        seed: int = 12345,
    ) -> WorldSuggestionResult:
        """Generate adversarial World suggestions for an approved property.

        Args:
            property_obj: The approved Property to target.
            available_tools: List of valid tool names or a RuntimeCapabilityBinding.
            seed: Seed for ID/stochastic derivation.

        Returns:
            WorldSuggestionResult with valid Worlds and rejected proposals.
        """
        self.budget.consume()

        tool_names: list[str] = []
        if available_tools is not None:
            if hasattr(available_tools, "bindings"):
                tool_names = list(set(available_tools.bindings.values()))
            elif isinstance(available_tools, list):
                tool_names = list(available_tools)

        prop_data = {
            "id": property_obj.id,
            "name": property_obj.name,
            "description": property_obj.description,
            "oracle_kind": property_obj.oracle.evaluator_kind,
            "oracle_details": property_obj.oracle.model_dump(mode="json"),
        }

        system_prompt, user_content = world_suggestion_prompt(
            property_json=json.dumps(prop_data, indent=2),
            available_tools=tool_names,
            response_schema=WorldProposalList,
        )

        response: WorldProposalList = self.provider.generate_structured(
            system_prompt=system_prompt,
            user_content=user_content,
            response_schema=WorldProposalList,
        )

        suggested_worlds: list[World] = []
        rejected_proposals: list[dict[str, str]] = []
        rng = random.Random(seed)

        for p in response.proposals:
            rejection_reason = self._validate_proposal(p, tool_names)
            if rejection_reason:
                rejected_proposals.append(
                    {"scenario": p.scenario_description, "reason": rejection_reason}
                )
                continue

            world = self._convert_proposal_to_world(p, property_obj, rng)
            suggested_worlds.append(world)

        return WorldSuggestionResult(
            suggested_worlds=suggested_worlds,
            rejected_proposals=rejected_proposals,
        )

    def _validate_proposal(
        self,
        p: WorldProposal,
        available_tools: list[str],
    ) -> str | None:
        """Validate proposal fields, tool references, and enum values."""
        # Validate tool override references if tool list is known
        if available_tools:
            for tool_name in p.tool_overrides:
                if tool_name not in available_tools:
                    return f"Tool override references unknown tool '{tool_name}' (available: {available_tools})."

        # Validate document trust levels
        for doc in p.documents:
            try:
                DocumentTrust(doc.trust)
            except ValueError:
                return f"Invalid document trust level '{doc.trust}'. Valid: {[t.value for t in DocumentTrust]}."

        # Validate tool behaviors
        for tool_name, override in p.tool_overrides.items():
            try:
                ToolBehavior(override.behavior)
            except ValueError:
                return f"Invalid tool behavior '{override.behavior}' for tool '{tool_name}'. Valid: {[b.value for b in ToolBehavior]}."

        return None

    def _convert_proposal_to_world(
        self,
        p: WorldProposal,
        property_obj: Property,
        rng: random.Random,
    ) -> World:
        """Convert a validated WorldProposal into a typed World domain model."""
        now = datetime.now(UTC)
        world_seed = rng.randint(0, 999999)

        docs = [
            WorldDocument(
                id=f"doc-{idx + 1}",
                trust=DocumentTrust(doc.trust),
                content=doc.content,
            )
            for idx, doc in enumerate(p.documents)
        ]

        tools = {
            tool_name: WorldToolConfig(
                behavior=ToolBehavior(override.behavior),
                error_message=override.error_message,
            )
            for tool_name, override in p.tool_overrides.items()
        }

        return World(
            id=new_id("VWORLD"),
            property_id=property_obj.id,
            property_stable_key=property_obj.stable_key,
            seed=world_seed,
            origin="model_assisted",
            input=WorldInput(message=p.input_message),
            retrieval=WorldRetrieval(documents=docs),
            tools=tools,
            created_at=now,
        )
