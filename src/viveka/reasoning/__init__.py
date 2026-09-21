"""
VIVEKA Phase 12 — Optional advisory reasoning enrichment.

This package provides structured model-assisted intelligence for VIVEKA's
deterministic verification pipeline. All output is advisory and never
replaces deterministic Phase 0-11 contracts.

With ``reasoning.mode = deterministic`` (default), this package performs
zero model calls and has zero effect on VIVEKA behavior.
"""

from __future__ import annotations

from viveka.reasoning.provider import ReasoningProvider
from viveka.reasoning.schemas import (
    AdvisoryDiagnosisNarrative,
    PropertyProposal,
    ReasoningProvenance,
    WorldProposal,
)

__all__ = [
    "AdvisoryDiagnosisNarrative",
    "PropertyProposal",
    "ReasoningProvenance",
    "ReasoningProvider",
    "WorldProposal",
]
