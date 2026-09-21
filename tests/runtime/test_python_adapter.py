"""Tests for PythonCallableAdapter (loading, execution, timeout enforcement)."""

import pytest

from viveka.core.ids import new_id
from viveka.runtime.models import (
    AgentRuntimeContext,
    RuntimeRequest,
    TargetSpec,
)
from viveka.runtime.python_adapter import AdapterError, PythonCallableAdapter
from viveka.runtime.vocabulary import ExecutionStatus, RuntimeAdapterType


def test_python_adapter_load_valid_target():
    adapter = PythonCallableAdapter()
    spec = TargetSpec(
        adapter_type=RuntimeAdapterType.PYTHON_CALLABLE,
        import_path="viveka.demo.agent:run_demo_agent",
    )
    adapter.load_target(spec)
    assert adapter.healthcheck() is True


def test_python_adapter_load_invalid_target():
    adapter = PythonCallableAdapter()
    spec = TargetSpec(import_path="non_existent_module:non_existent_func")
    with pytest.raises(AdapterError, match="Could not load target"):
        adapter.load_target(spec)


def test_python_adapter_execute_demo_agent():
    adapter = PythonCallableAdapter()
    spec = TargetSpec(import_path="viveka.demo.agent:run_demo_agent")

    req = RuntimeRequest(
        execution_id=new_id("VRUN"),
        world_id="VWORLD-01",
        target=spec,
        context=AgentRuntimeContext(message="Hello support"),
        seed=123,
        timeout_seconds=5.0,
    )

    res = adapter.execute(req)
    assert res.status == ExecutionStatus.SUCCESS
    assert len(res.events) > 0
    assert len(res.final_output) > 0
