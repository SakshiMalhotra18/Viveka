"""
Advisory call budget tracker for VIVEKA Phase 12.

Enforces a maximum number of model calls per invocation to prevent
unbounded cost and latency.
"""

from __future__ import annotations

from viveka.core.errors import ProviderError


class AdvisoryBudget:
    """Tracks and enforces advisory model call limits.

    Raises ``ProviderError`` when the budget is exhausted.
    """

    def __init__(self, max_calls: int = 20) -> None:
        if max_calls < 0:
            raise ValueError(f"max_calls must be >= 0, got {max_calls}")
        self._max_calls = max_calls
        self._calls_made = 0

    @property
    def max_calls(self) -> int:
        """Maximum allowed advisory calls."""
        return self._max_calls

    @property
    def calls_made(self) -> int:
        """Number of advisory calls made so far."""
        return self._calls_made

    @property
    def remaining(self) -> int:
        """Number of advisory calls remaining."""
        return max(0, self._max_calls - self._calls_made)

    @property
    def exhausted(self) -> bool:
        """Whether the budget has been fully consumed."""
        return self._calls_made >= self._max_calls

    def consume(self) -> None:
        """Consume one advisory call from the budget.

        Raises:
            ProviderError: If the budget is exhausted.
        """
        if self.exhausted:
            raise ProviderError(
                f"Advisory call budget exhausted ({self._max_calls} calls used). "
                "Increase reasoning.max_advisory_calls or reduce advisory scope.",
                hint="Set a higher max_advisory_calls in .viveka/config.yaml.",
            )
        self._calls_made += 1
