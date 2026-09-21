"""Unit tests for verification models."""

from viveka.verification.models import (
    PropertyVerificationResult,
    VerificationResult,
)
from viveka.verification.vocabulary import PropertyVerificationStatus, VerificationOutcome


def test_verification_models_serialization() -> None:
    pr = PropertyVerificationResult(
        property_id="VPROP-01",
        property_name="test-prop",
        property_stable_key="flow:test",
        property_revision=1,
        status=PropertyVerificationStatus.NO_REPRODUCED_VIOLATION,
        worlds_tested=2,
        worlds_violated=0,
    )
    vr = VerificationResult(
        outcome=VerificationOutcome.NO_REPRODUCED_VIOLATIONS,
        properties_considered=1,
        properties_verified=1,
        properties_passed=1,
        properties_violated=0,
        total_worlds_tested=2,
        property_results=[pr],
        summary_message="Clean run",
    )

    dumped = vr.model_dump(mode="json")
    assert dumped["outcome"] == "no_reproduced_violations"
    assert len(dumped["property_results"]) == 1
    assert dumped["property_results"][0]["status"] == "no_reproduced_violation"

    loaded = VerificationResult.model_validate(dumped)
    assert loaded.outcome == VerificationOutcome.NO_REPRODUCED_VIOLATIONS
    assert loaded.properties_passed == 1
