"""
VIVEKA Phase 8: Trace, Property Evaluation, and Reproduction Package.

Provides trace normalization, capability binding providers, locked verdict evaluators,
property/world integrity checks, deterministic SHA-256 seed derivation, and reproduction testing.
"""

from __future__ import annotations

from viveka.evaluation.binding import get_demo_capability_binding
from viveka.evaluation.contracts import (
    DemoOutputClaimClassifier,
    OutputClaimClassifier,
)
from viveka.evaluation.evaluators import (
    EVALUATOR_REGISTRY,
    BasePropertyEvaluator,
    FailureHandledEvaluator,
    FlowForbiddenEvaluator,
)
from viveka.evaluation.exceptions import (
    EvaluationError,
    PropertyNotApprovedError,
    PropertyWorldMismatchError,
)
from viveka.evaluation.models import (
    EvaluationContext,
    EvaluationEvidence,
    EvaluationResult,
    ExecutionTrace,
    ReproductionPolicy,
    ReproductionResult,
    ReproductionRun,
    RuntimeCapabilityBinding,
)
from viveka.evaluation.reproduction import (
    derive_run_seed,
    execute_reproduction,
)
from viveka.evaluation.resolvers import resolve_allowed_exception
from viveka.evaluation.trace import normalize_trace
from viveka.evaluation.vocabulary import EvaluationVerdict

__all__ = [
    "EVALUATOR_REGISTRY",
    "BasePropertyEvaluator",
    "DemoOutputClaimClassifier",
    "EvaluationContext",
    "EvaluationError",
    "EvaluationEvidence",
    "EvaluationResult",
    "EvaluationVerdict",
    "ExecutionTrace",
    "FailureHandledEvaluator",
    "FlowForbiddenEvaluator",
    "OutputClaimClassifier",
    "PropertyNotApprovedError",
    "PropertyWorldMismatchError",
    "ReproductionPolicy",
    "ReproductionResult",
    "ReproductionRun",
    "RuntimeCapabilityBinding",
    "derive_run_seed",
    "execute_reproduction",
    "get_demo_capability_binding",
    "normalize_trace",
    "resolve_allowed_exception",
]
