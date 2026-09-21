"""
Controlled vocabularies for VIVEKA Phase 8 evaluation models.

Defines locked verdict outcomes for property oracle evaluation.
"""

from __future__ import annotations

from enum import StrEnum


class EvaluationVerdict(StrEnum):
    """Locked evaluation verdict outcomes.

    Semantics:
      - VIOLATION: Observable trace evidence proves prohibited behavior occurred.
      - NO_OBSERVED_VIOLATION: Property trigger occurred and prohibited outcome was not observed.
      - NOT_APPLICABLE: Property trigger did not occur (e.g. source capability was never invoked).
      - INCONCLUSIVE: VIVEKA lacks sufficient trustworthy evidence (e.g. missing capability binding,
        execution error/timeout, or free-form natural language output requiring LLM reasoning).
    """

    VIOLATION = "violation"
    NO_OBSERVED_VIOLATION = "no_observed_violation"
    INCONCLUSIVE = "inconclusive"
    NOT_APPLICABLE = "not_applicable"
