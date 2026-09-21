"""Unit tests for verification vocabulary."""

from viveka.verification.vocabulary import PropertyVerificationStatus, VerificationOutcome


def test_verification_vocabulary_values() -> None:
    assert VerificationOutcome.NO_REPRODUCED_VIOLATIONS == "no_reproduced_violations"
    assert VerificationOutcome.REPRODUCED_VIOLATIONS_FOUND == "reproduced_violations_found"
    assert VerificationOutcome.NO_APPROVED_PROPERTIES == "no_approved_properties"
    assert VerificationOutcome.EXECUTION_ERROR == "execution_error"
    assert VerificationOutcome.INCOMPLETE == "incomplete"

    assert PropertyVerificationStatus.NO_REPRODUCED_VIOLATION == "no_reproduced_violation"
    assert PropertyVerificationStatus.REPRODUCED_VIOLATION == "reproduced_violation"
    assert PropertyVerificationStatus.ERROR == "error"
    assert PropertyVerificationStatus.INCONCLUSIVE == "inconclusive"
    assert PropertyVerificationStatus.SKIPPED == "skipped"


def test_no_safety_overclaim_wording() -> None:
    for outcome in VerificationOutcome:
        assert "safe" not in outcome.value.lower()
        assert "proved_safe" not in outcome.value.lower()
        assert "proven_safe" not in outcome.value.lower()
    for status in PropertyVerificationStatus:
        assert "safe" not in status.value.lower()
        assert "passed" not in status.value.lower()
        assert "violated" != status.value.lower()
