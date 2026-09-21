"""
Controlled vocabularies for VIVEKA Phase 7 runtime models.

Defines typed enumerations for adapter kinds, execution status, and raw event types.
"""

from __future__ import annotations

from enum import StrEnum


class RuntimeAdapterType(StrEnum):
    """Supported or planned runtime adapter categories."""

    PYTHON_CALLABLE = "python_callable"
    """In-process/child-process execution of Python callable entrypoints."""

    HTTP = "http"
    """HTTP endpoint communication (deferred)."""

    MCP = "mcp"
    """Model Context Protocol server communication (deferred)."""


class ExecutionStatus(StrEnum):
    """Outcome status of a target execution run."""

    SUCCESS = "success"
    """Target completed execution normally."""

    TARGET_ERROR = "target_error"
    """Target raised an uncaught runtime exception."""

    ADAPTER_ERROR = "adapter_error"
    """Adapter failed to load or invoke the target."""

    TIMEOUT = "timeout"
    """Target execution exceeded the configured timeout_seconds."""

    UNSUPPORTED_FEATURE = "unsupported_feature"
    """World contained features unsupported by the target or adapter."""


class RawEventType(StrEnum):
    """Category of raw observable runtime events."""

    TOOL_CALL = "tool_call"
    """Agent initiated a tool call with arguments."""

    TOOL_RESULT = "tool_result"
    """Tool returned a response or raised a tool-level error."""

    AGENT_OUTPUT = "agent_output"
    """Agent produced text output."""

    RUNTIME_ERROR = "runtime_error"
    """Runtime framework or system error occurred."""


class EventOrigin(StrEnum):
    """Provenance origin of an observable runtime event."""

    VIVEKA_OBSERVED = "viveka_observed"
    """Independently observed telemetry generated directly by VIVEKA framework wrappers."""

    TARGET_REPORTED = "target_reported"
    """Telemetry self-reported by target agent service via instrumentation contract."""
