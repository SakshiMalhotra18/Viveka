"""
Abstract Base Class for VIVEKA Phase 7 runtime adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from viveka.runtime.models import RuntimeRequest, RuntimeResult, TargetSpec


class BaseRuntimeAdapter(ABC):
    """Abstract Base Class interface for all runtime execution adapters."""

    @abstractmethod
    def load_target(self, spec: TargetSpec) -> None:
        """Load and prepare the target execution environment according to *spec*.

        Raises:
            AdapterError: If loading fails or the target cannot be resolved.
        """

    @abstractmethod
    def execute(self, request: RuntimeRequest) -> RuntimeResult:
        """Execute a single trial run against the target.

        Args:
            request: The execution request specifying world context, target, seed, timeout.

        Returns:
            A :class:`RuntimeResult` detailing execution status, raw events, and output.
        """

    @abstractmethod
    def healthcheck(self) -> bool:
        """Return True if the adapter and loaded target are ready for execution."""
