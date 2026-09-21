"""
Unit tests for AdvisoryBudget and shared session budget enforcement.
"""

from __future__ import annotations

import pytest

from viveka.capabilities.models import (
    Capability,
    CapabilityAnalysisResult,
    CapabilityEvidence,
)
from viveka.capabilities.vocabulary import (
    CapabilityTag,
    Externality,
    Reversibility,
    SideEffect,
    TrustRole,
)
from viveka.core.errors import ProviderError
from viveka.core.ids import new_id
from viveka.diagnosis.models import Diagnosis
from viveka.properties.models import FlowForbiddenOracle, Property
from viveka.properties.vocabulary import PropertyStatus
from viveka.reasoning.advisors.diagnosis_enricher import DiagnosisEnricher
from viveka.reasoning.advisors.property_advisor import PropertySuggestionAdvisor
from viveka.reasoning.advisors.world_advisor import WorldSuggestionAdvisor
from viveka.reasoning.budget import AdvisoryBudget
from viveka.reasoning.fake import FakeReasoningProvider
from viveka.reasoning.schemas import (
    AdvisoryDiagnosisNarrative,
    PropertyProposalList,
    WorldProposalList,
)


def test_budget_consumption_and_tracking() -> None:
    budget = AdvisoryBudget(max_calls=3)
    assert budget.max_calls == 3
    assert budget.calls_made == 0
    assert budget.remaining == 3
    assert not budget.exhausted

    budget.consume()
    assert budget.calls_made == 1
    assert budget.remaining == 2

    budget.consume()
    budget.consume()
    assert budget.calls_made == 3
    assert budget.remaining == 0
    assert budget.exhausted

    with pytest.raises(ProviderError, match="Advisory call budget exhausted"):
        budget.consume()


def test_budget_zero_calls() -> None:
    budget = AdvisoryBudget(max_calls=0)
    assert budget.exhausted
    with pytest.raises(ProviderError, match="budget exhausted"):
        budget.consume()


def test_invalid_budget_raises() -> None:
    with pytest.raises(ValueError, match="max_calls must be >= 0"):
        AdvisoryBudget(max_calls=-1)


def test_shared_budget_across_multiple_advisors() -> None:
    """Proves that multiple Phase 12 advisors consume from the same shared budget."""
    shared_budget = AdvisoryBudget(max_calls=2)
    fake_provider = FakeReasoningProvider(
        canned_responses={
            PropertyProposalList: PropertyProposalList(proposals=[]),
            WorldProposalList: WorldProposalList(proposals=[]),
            AdvisoryDiagnosisNarrative: AdvisoryDiagnosisNarrative(narrative="Narrative"),
        }
    )

    prop_advisor = PropertySuggestionAdvisor(fake_provider, budget=shared_budget)
    world_advisor = WorldSuggestionAdvisor(fake_provider, budget=shared_budget)
    diag_enricher = DiagnosisEnricher(fake_provider, budget=shared_budget)

    # 1. First call from prop advisor consumes 1
    analysis = CapabilityAnalysisResult(
        capabilities=[
            Capability(
                id=new_id("VCAP"),
                name="Tool",
                source_symbol="tool",
                source_file="src/t.py",
                source_line=1,
                tags=[CapabilityTag.RETRIEVAL],
                confidence="high",
                side_effect=SideEffect.READ_ONLY,
                externality=Externality.LOCAL,
                reversibility=Reversibility.REVERSIBLE,
                trust_role=TrustRole.UNTRUSTED_INGRESS,
                evidence=[
                    CapabilityEvidence(
                        evidence_type="call", value="f", file_path="src/t.py", line=1
                    )
                ],
            )
        ]
    )
    prop_advisor.suggest(analysis)
    assert shared_budget.calls_made == 1
    assert shared_budget.remaining == 1

    # 2. Second call from world advisor consumes 1
    prop = Property(
        id=new_id("VPROP"),
        stable_key="test-key",
        name="test",
        description="desc",
        status=PropertyStatus.APPROVED,
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="src/t.py::tool",
            forbidden_sink_key="src/t.py::tool",
        ),
    )
    world_advisor.suggest(prop)
    assert shared_budget.calls_made == 2
    assert shared_budget.remaining == 0
    assert shared_budget.exhausted

    # 3. Third call from diagnosis enricher must fail with ProviderError
    diag = Diagnosis(
        diag_id=new_id("VDIAG"),
        diagnosis_method="deterministic_template_v1",
        reduction_id=new_id("VRED"),
        property_id=prop.id,
        property_stable_key=prop.stable_key,
        property_revision=1,
        world_id=new_id("VWORLD"),
        original_world_id=new_id("VWORLD"),
        expected_behavior="exp",
        observed_behavior="obs",
        reproduction_summary="sum",
    )
    with pytest.raises(ProviderError, match="Advisory call budget exhausted"):
        diag_enricher.enrich(diag)
