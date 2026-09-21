"""
VIVEKA Phase 9: Reproducible Failure Reduction Engine Package.

Provides greedy structural failure reduction for Phase 6 Worlds, preserving
Phase 8 reproduction criteria under deterministic shared stochastic seed derivation.
"""

from __future__ import annotations

from viveka.reduction.engine import ReductionEngine
from viveka.reduction.fingerprint import compute_world_fingerprint
from viveka.reduction.models import (
    ReductionBudget,
    ReductionCandidate,
    ReductionResult,
    ReductionStep,
)
from viveka.reduction.operators import generate_reduction_candidates
from viveka.reduction.runner import (
    DefaultReproductionRunner,
)
from viveka.reduction.runner import (
    ReproductionRunnerProtocol as ReproductionRunnerProtocol,
)
from viveka.reduction.store import ReductionNotFoundError, ReductionStore
from viveka.reduction.vocabulary import ReductionOperator, ReductionStopReason

__all__ = [
    "DefaultReproductionRunner",
    "ReductionBudget",
    "ReductionCandidate",
    "ReductionEngine",
    "ReductionNotFoundError",
    "ReductionOperator",
    "ReductionResult",
    "ReductionRunnerProtocol",
    "ReductionStep",
    "ReductionStopReason",
    "ReductionStore",
    "compute_world_fingerprint",
    "generate_reduction_candidates",
]
