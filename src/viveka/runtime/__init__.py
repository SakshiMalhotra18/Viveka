"""
VIVEKA Phase 7: Runtime Package.

Provides typed target specifications, sanitized runtime contexts, abstract runtime
adapters, Python callable execution with process isolation and timeout enforcement,
VIVEKA-owned telemetry collection, and runtime result models.
"""

from __future__ import annotations

from viveka.runtime.adapter import BaseRuntimeAdapter
from viveka.runtime.collector import EventCollector, wrap_tool
from viveka.runtime.factory import create_adapter
from viveka.runtime.http_adapter import HttpJsonRuntimeAdapter, is_local_target_endpoint
from viveka.runtime.mapper import UnsupportedWorldFeatureError, map_world_to_context
from viveka.runtime.models import (
    AgentAuthorizationContext,
    AgentDocumentContext,
    AgentEnvironmentContext,
    AgentRuntimeContext,
    AgentStateContext,
    AgentToolConfigContext,
    AgentUserContext,
    RawEvent,
    RuntimeRequest,
    RuntimeResult,
    TargetSpec,
)
from viveka.runtime.python_adapter import AdapterError, PythonCallableAdapter
from viveka.runtime.vocabulary import (
    ExecutionStatus,
    RawEventType,
    RuntimeAdapterType,
)

__all__ = [
    "AdapterError",
    "AgentAuthorizationContext",
    "AgentDocumentContext",
    "AgentEnvironmentContext",
    "AgentRuntimeContext",
    "AgentStateContext",
    "AgentToolConfigContext",
    "AgentUserContext",
    "BaseRuntimeAdapter",
    "EventCollector",
    "ExecutionStatus",
    "HttpJsonRuntimeAdapter",
    "PythonCallableAdapter",
    "RawEvent",
    "RawEventType",
    "RuntimeAdapterType",
    "RuntimeRequest",
    "RuntimeResult",
    "TargetSpec",
    "UnsupportedWorldFeatureError",
    "create_adapter",
    "is_local_target_endpoint",
    "map_world_to_context",
    "wrap_tool",
]
