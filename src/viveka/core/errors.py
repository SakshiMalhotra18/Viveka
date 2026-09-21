"""
Core error hierarchy for VIVEKA.

All VIVEKA errors inherit from VivekaError.
The CLI catches VivekaError at the top level and renders it with Rich
so users always receive a useful, actionable message rather than a raw traceback.

Error categories follow Section 40 of the product specification.
"""

from __future__ import annotations


class VivekaError(Exception):
    """Base class for all VIVEKA errors.

    Attributes:
        message: Human-readable description of the problem.
        hint: Optional actionable suggestion for the user.
    """

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        return self.message


class ConfigurationError(VivekaError):
    """Raised when VIVEKA configuration is missing, invalid, or contradictory."""


class InspectionError(VivekaError):
    """Raised when repository inspection fails (I/O, parsing, path safety)."""


class ProviderError(VivekaError):
    """Raised when a reasoning provider fails to respond or returns unusable output."""


class TargetStartupError(VivekaError):
    """Raised when the target agent process cannot be started or does not become healthy."""


class TargetInvocationError(VivekaError):
    """Raised when invoking the target agent during a trial fails."""


class TraceError(VivekaError):
    """Raised when trace collection or parsing fails."""


class PropertyError(VivekaError):
    """Raised when a property definition is malformed or cannot be evaluated."""


class StorageError(VivekaError):
    """Raised when SQLite or file-system storage operations fail."""


class SandboxError(VivekaError):
    """Raised when the sandbox/isolation layer encounters an error."""


class InternalError(VivekaError):
    """
    Raised when VIVEKA encounters an unexpected internal condition.

    If a user sees this, it is a VIVEKA bug.  The message should always
    include a suggestion to file an issue.
    """

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            hint="This is likely a VIVEKA bug. Please file an issue with the full error output.",
        )
