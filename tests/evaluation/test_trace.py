"""Tests for Phase 8 trace normalization and ExecutionStatus preservation."""

from viveka.core.ids import new_id
from viveka.evaluation.trace import normalize_trace
from viveka.runtime.models import RawEvent, RuntimeResult
from viveka.runtime.vocabulary import ExecutionStatus, RawEventType


def test_normalize_trace_sorts_events_and_preserves_status():
    evt1 = RawEvent(
        sequence=2,
        event_id=new_id("VEVT"),
        event_type=RawEventType.TOOL_RESULT,
        call_id="call-1",
        tool_name="knowledge.search",
        tool_result={"results": []},
    )
    evt2 = RawEvent(
        sequence=1,
        event_id=new_id("VEVT"),
        event_type=RawEventType.TOOL_CALL,
        call_id="call-1",
        tool_name="knowledge.search",
        tool_args={"query": "test"},
    )

    res = RuntimeResult(
        execution_id=new_id("VRUN"),
        world_id="VWORLD-01",
        status=ExecutionStatus.TIMEOUT,
        events=[evt1, evt2],
        final_output="",
    )

    trace = normalize_trace(res)

    assert trace.status == ExecutionStatus.TIMEOUT
    assert len(trace.events) == 2
    assert trace.events[0].sequence == 1
    assert trace.events[1].sequence == 2
    assert "knowledge.search" in trace.calls_by_name
    assert "call-1" in trace.results_by_call_id
