"""
Exceptions for VIVEKA Phase 8 evaluation integrity checks.
"""

from __future__ import annotations

from viveka.core.errors import VivekaError


class EvaluationError(VivekaError):
    """Base exception for evaluation phase errors."""


class PropertyNotApprovedError(EvaluationError):
    """Raised when evaluation is attempted on a property that is not APPROVED."""


class PropertyWorldMismatchError(EvaluationError):
    """Raised when a World's property_stable_key does not match the Property's stable_key."""
