"""
Trace normalization for VIVEKA Phase 8.

Converts Phase 7 RuntimeResult into a structured ExecutionTrace, sorting raw events
by 1-indexed sequence number, indexing TOOL_CALL events by tool name, correlating
TOOL_RESULT events by call_id, and preserving ExecutionStatus.
"""

from __future__ import annotations

from viveka.core.ids import new_id
from viveka.evaluation.models import ExecutionTrace
from viveka.runtime.models import RawEvent, RuntimeResult
from viveka.runtime.vocabulary import RawEventType


def normalize_trace(result: RuntimeResult) -> ExecutionTrace:
    """Convert RuntimeResult into structured ExecutionTrace.

    Sorts events by sequence number, preserves Phase 7 ExecutionStatus,
    indexes TOOL_CALL events by tool name, and correlates TOOL_RESULT events by call_id.
    """
    sorted_events = sorted(result.events, key=lambda e: e.sequence)

    calls_by_name: dict[str, list[RawEvent]] = {}
    results_by_call_id: dict[str, RawEvent] = {}

    for evt in sorted_events:
        if evt.event_type == RawEventType.TOOL_CALL and evt.tool_name:
            calls_by_name.setdefault(evt.tool_name, []).append(evt)
        elif evt.event_type == RawEventType.TOOL_RESULT and evt.call_id:
            results_by_call_id[evt.call_id] = evt

    return ExecutionTrace(
        trace_id=new_id("VTRC"),
        execution_id=result.execution_id,
        world_id=result.world_id,
        status=result.status,
        events=sorted_events,
        calls_by_name=calls_by_name,
        results_by_call_id=results_by_call_id,
        final_output=result.final_output,
    )
