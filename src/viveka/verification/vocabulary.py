"""
Vocabulary enums for VIVEKA Phase 11 verification orchestration.
"""

from __future__ import annotations

from enum import StrEnum


class VerificationOutcome(StrEnum):
    """Top-level factual outcome of a `viveka verify` run.

    Explicitly avoids safety overclaims (no SAFE / UNSAFE / PROVED_SAFE).
    """

    NO_REPRODUCED_VIOLATIONS = "no_reproduced_violations"
    REPRODUCED_VIOLATIONS_FOUND = "reproduced_violations_found"
    NO_APPROVED_PROPERTIES = "no_approved_properties"
    EXECUTION_ERROR = "execution_error"
    INCOMPLETE = "incomplete"


class PropertyVerificationStatus(StrEnum):
    """Per-property verification outcome."""

    NO_REPRODUCED_VIOLATION = "no_reproduced_violation"
    REPRODUCED_VIOLATION = "reproduced_violation"
    ERROR = "error"
    INCONCLUSIVE = "inconclusive"
    SKIPPED = "skipped"
