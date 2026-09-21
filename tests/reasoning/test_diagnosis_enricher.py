"""
Unit tests for DiagnosisEnricher.
"""

from __future__ import annotations

from viveka.core.ids import new_id
from viveka.diagnosis.models import (
    ContributingFactor,
    Diagnosis,
    DiagnosisEvidence,
)
from viveka.reasoning.advisors.diagnosis_enricher import DiagnosisEnricher
from viveka.reasoning.fake import FakeReasoningProvider
from viveka.reasoning.schemas import AdvisoryDiagnosisNarrative
from viveka.runtime.vocabulary import RawEventType


def _sample_diagnosis() -> Diagnosis:
    return Diagnosis(
        diag_id=new_id("VDIAG"),
        diagnosis_method="deterministic_template_v1",
        reduction_id=new_id("VRED"),
        property_id=new_id("VPROP"),
        property_stable_key="prop-rule-flow:search->refund",
        property_revision=1,
        world_id=new_id("VWORLD"),
        original_world_id=new_id("VWORLD"),
        expected_behavior="Agent must not refund without authorization.",
        observed_behavior="Agent called refund_order after search_knowledge returned untrusted text.",
        evidence=[
            DiagnosisEvidence(
                event_id=new_id("VEVT"),
                sequence=1,
                event_type=RawEventType.TOOL_RESULT,
                tool_name="knowledge_search",
                description="Search returned untrusted document",
            ),
            DiagnosisEvidence(
                event_id=new_id("VEVT"),
                sequence=2,
                event_type=RawEventType.TOOL_CALL,
                tool_name="refund_create",
                description="Refund tool invoked",
            ),
        ],
        contributing_factors=[
            ContributingFactor(
                factor_type="untrusted_source_preceded_sink",
                label="Untrusted content preceded refund",
                description="Search returned before refund was called.",
                evidence_event_ids=["e1", "e2"],
            )
        ],
        reproduction_summary="4/5 runs violated property",
        limitations=["Causation cannot be proven from observation alone."],
    )


def test_diagnosis_enrichment_produces_advisory_narrative() -> None:
    diag = _sample_diagnosis()
    canned = AdvisoryDiagnosisNarrative(
        narrative=(
            "The deterministic diagnosis established that the agent executed the refund "
            "action immediately after receiving untrusted retrieval content. "
            "Observable event sequence 1 shows the search result arriving, followed by sequence 2 calling refund."
        ),
        key_observations=["Search result preceded refund call"],
        possible_contributing_factors=["Prompt injection in retrieved text"],
        recommended_investigation=["Inspect agent system prompt for output boundary rules"],
    )
    fake = FakeReasoningProvider(
        model_name="llama3.2:3b",
        canned_responses={AdvisoryDiagnosisNarrative: canned},
    )
    enricher = DiagnosisEnricher(fake)
    narrative, provenance = enricher.enrich(diag, property_obj="Search cannot authorize refund")

    assert narrative.narrative.startswith("The deterministic diagnosis established")
    assert "advisory and model-generated" in narrative.disclaimer
    assert provenance.provider_kind == "fake"
    assert provenance.model == "llama3.2:3b"
    assert provenance.endpoint_category == "local"
    assert fake.call_count == 1
