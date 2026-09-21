"""Tests for Phase 7 runtime models."""

from viveka.core.ids import new_id
from viveka.runtime.models import (
    RawEvent,
    RuntimeResult,
    TargetSpec,
)
from viveka.runtime.vocabulary import ExecutionStatus, RawEventType, RuntimeAdapterType


def test_target_spec_defaults():
    spec = TargetSpec(import_path="viveka.demo.agent:run_demo_agent")
    assert spec.adapter_type == RuntimeAdapterType.PYTHON_CALLABLE
    assert spec.import_path == "viveka.demo.agent:run_demo_agent"
    assert spec.working_directory == "."


def test_raw_event_sequence_and_call_id():
    evt1 = RawEvent(
        sequence=1,
        event_id=new_id("VEVT"),
        event_type=RawEventType.TOOL_CALL,
        call_id="call-1234",
        tool_name="refund.create",
        tool_args={"order_id": "5832"},
    )
    evt2 = RawEvent(
        sequence=2,
        event_id=new_id("VEVT"),
        event_type=RawEventType.TOOL_RESULT,
        call_id="call-1234",
        tool_name="refund.create",
        tool_result={"status": "success"},
    )

    assert evt1.sequence == 1
    assert evt2.sequence == 2
    assert evt1.call_id == evt2.call_id == "call-1234"


def test_runtime_result_serialization():
    exec_id = new_id("VRUN")
    res = RuntimeResult(
        execution_id=exec_id,
        world_id="VWORLD-01",
        status=ExecutionStatus.SUCCESS,
        final_output="Refund processed successfully",
        events=[
            RawEvent(
                sequence=1,
                event_id=new_id("VEVT"),
                event_type=RawEventType.AGENT_OUTPUT,
                output_text="Done",
            )
        ],
    )

    dumped = res.model_dump(mode="json")
    reloaded = RuntimeResult.model_validate(dumped)

    assert reloaded.execution_id == exec_id
    assert reloaded.status == ExecutionStatus.SUCCESS
    assert len(reloaded.events) == 1
    assert reloaded.events[0].sequence == 1
