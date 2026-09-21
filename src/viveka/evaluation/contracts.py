"""
Output claim classifier contracts for VIVEKA Phase 8 FailureHandledEvaluator.

Provides an abstract OutputClaimClassifier interface and a target-specific
DemoOutputClaimClassifier. Prevents embedding target-specific strings or generic
English substring matching inside universal evaluators.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class OutputClaimClassifier(ABC):
    """Abstract interface for target-specific output claim classification."""

    @abstractmethod
    def claims_success(self, output_text: str, failed_tool: str) -> bool | None:
        """Classify whether output_text represents failed_tool action as successful.

        Returns:
            True if text claims action succeeded when tool failed.
            False if text truthfully communicates failure.
            None if text is ambiguous or cannot be classified deterministically.
        """


class DemoOutputClaimClassifier(OutputClaimClassifier):
    """Deterministic output claim classifier for VIVEKA Demo Agent."""

    def claims_success(self, output_text: str, failed_tool: str) -> bool | None:
        out_lower = output_text.lower()
        # Explicit demo contract success claims
        if "processed successfully" in out_lower or "retry succeeded" in out_lower:
            return True
        if (
            "failed" in out_lower
            or "error" in out_lower
            or "could not" in out_lower
            or "cannot" in out_lower
        ):
            return False
        return None
