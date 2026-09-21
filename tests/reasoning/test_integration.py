"""
Lightweight Phase 11 -> 12 integration test.

Demonstrates:
  deterministic VIVEKA artifact
    -> FakeReasoningProvider
    -> typed advisory suggestion/enrichment
    -> validation
    -> candidate saved as CANDIDATE (never auto-verified)
    -> deterministic verification outcome remains completely unchanged
"""

from __future__ import annotations

from pathlib import Path

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
from viveka.core.ids import new_id
from viveka.evaluation.binding import get_demo_capability_binding
from viveka.evaluation.models import ReproductionPolicy
from viveka.properties.models import FlowForbiddenOracle, Property
from viveka.properties.store import PropertyStore
from viveka.properties.vocabulary import (
    InvariantType,
    PropertySource,
    PropertyStatus,
)
from viveka.reasoning.advisors.property_advisor import PropertySuggestionAdvisor
from viveka.reasoning.fake import FakeReasoningProvider
from viveka.reasoning.schemas import (
    AdvisoryDiagnosisNarrative,
    PropertyProposal,
    PropertyProposalList,
)
from viveka.runtime.models import TargetSpec
from viveka.verification.engine import VerificationEngine
from viveka.verification.vocabulary import VerificationOutcome


def test_phase12_advisory_integration(tmp_path: Path) -> None:
    # 1. Setup approved property
    prop_store = PropertyStore(tmp_path)
    approved_prop = Property(
        id=new_id("VPROP"),
        stable_key="prop-rule-flow:forbidden_flow:search->refund",
        name="approved-search-refund-invariant",
        description="Search results cannot authorize refunds.",
        status=PropertyStatus.APPROVED,
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="src/search.py::search_knowledge",
            forbidden_sink_key="src/tools.py::refund_order",
        ),
    )
    prop_store.save(approved_prop)

    # 2. Setup capability analysis
    cap1 = Capability(
        id=new_id("VCAP"),
        name="Knowledge Search",
        source_symbol="search_knowledge",
        source_file="src/search.py",
        source_line=10,
        tags=[CapabilityTag.RETRIEVAL],
        confidence="high",
        side_effect=SideEffect.READ_ONLY,
        externality=Externality.EXTERNAL,
        reversibility=Reversibility.REVERSIBLE,
        trust_role=TrustRole.UNTRUSTED_INGRESS,
        evidence=[
            CapabilityEvidence(
                evidence_type="call",
                value="requests.get",
                file_path="src/search.py",
                line=12,
            )
        ],
    )
    cap2 = Capability(
        id=new_id("VCAP"),
        name="Refund Order",
        source_symbol="refund_order",
        source_file="src/tools.py",
        source_line=25,
        tags=[CapabilityTag.FINANCIAL_WRITE],
        confidence="high",
        side_effect=SideEffect.MUTATING,
        externality=Externality.EXTERNAL,
        reversibility=Reversibility.IRREVERSIBLE,
        trust_role=TrustRole.PRIVILEGED_SINK,
        evidence=[
            CapabilityEvidence(
                evidence_type="call",
                value="stripe.Refund.create",
                file_path="src/tools.py",
                line=30,
            )
        ],
    )
    analysis = CapabilityAnalysisResult(capabilities=[cap1, cap2])

    # 3. Model suggests a new candidate property
    proposal = PropertyProposal(
        name="suggested-extra-invariant",
        description="Model suggested extra invariant.",
        invariant_type=InvariantType.FORBIDDEN_FLOW,
        source_capability_key="src/search.py::search_knowledge",
        sink_capability_key="src/tools.py::refund_order",
        rationale="Extra safety check.",
        evidence_description="Observed data path.",
    )
    fake_provider = FakeReasoningProvider(
        canned_responses={
            PropertyProposalList: PropertyProposalList(proposals=[proposal]),
            AdvisoryDiagnosisNarrative: AdvisoryDiagnosisNarrative(
                narrative="Advisory narrative for observed diagnosis."
            ),
        }
    )

    advisor = PropertySuggestionAdvisor(fake_provider)
    sugg_res = advisor.suggest(analysis, existing_catalog=prop_store.load_catalog())
    assert len(sugg_res.suggested_candidates) == 1

    model_prop = sugg_res.suggested_candidates[0]
    assert model_prop.status == PropertyStatus.CANDIDATE  # Never approved
    assert model_prop.source == PropertySource.MODEL_ASSISTED
    prop_store.save(model_prop)

    # 4. Run verification: prove model-suggested candidate is NOT auto-verified
    target_spec = TargetSpec(
        adapter_type="python_callable",
        import_path="viveka.demo.agent:run_demo_agent",
    )
    binding = get_demo_capability_binding()

    engine = VerificationEngine(project_root=tmp_path)
    res = engine.verify(
        policy=ReproductionPolicy(runs=1, minimum_violations=1),
        max_worlds_per_property=1,
        target_spec=target_spec,
        binding=binding,
        enrich=True,
        reasoning_provider=fake_provider,
    )

    # Only 1 property verified (the approved one, not the candidate)
    assert res.properties_verified == 1
    assert res.candidate_properties_count == 1
    assert res.properties_considered == 1
    assert res.outcome in (
        VerificationOutcome.NO_REPRODUCED_VIOLATIONS,
        VerificationOutcome.REPRODUCED_VIOLATIONS_FOUND,
    )
