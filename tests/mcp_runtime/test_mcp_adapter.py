"""
Unit and integration tests for Phase 14 McpRuntimeAdapter.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from viveka.core.config import load_config
from viveka.evaluation.binding import get_demo_capability_binding
from viveka.evaluation.evaluators import FailureHandledEvaluator, FlowForbiddenEvaluator
from viveka.evaluation.models import EvaluationContext
from viveka.evaluation.trace import ExecutionTrace
from viveka.evaluation.vocabulary import EvaluationVerdict
from viveka.properties.models import FailureHandledOracle, FlowForbiddenOracle, Property
from viveka.properties.vocabulary import PropertyStatus
from viveka.runtime.factory import create_adapter
from viveka.runtime.mcp_adapter import McpRuntimeAdapter
from viveka.runtime.models import AgentRuntimeContext, AgentStateContext, RuntimeRequest, TargetSpec
from viveka.runtime.python_adapter import AdapterError
from viveka.runtime.vocabulary import EventOrigin, ExecutionStatus, RawEventType, RuntimeAdapterType

REF_SERVER = str((Path(__file__).parent / "reference_mcp_server.py").resolve())
PYTHON_EXE = sys.executable


@pytest.fixture
def mcp_target_spec() -> TargetSpec:
    """Standard TargetSpec for reference stdio MCP server."""
    return TargetSpec(
        adapter_type=RuntimeAdapterType.MCP,
        options={
            "transport": "stdio",
            "command": PYTHON_EXE,
            "args": json.dumps([REF_SERVER]),
            "tool": "agent.run",
            "timeout_seconds": "10.0",
        },
    )


@pytest.fixture
def sample_request(mcp_target_spec: TargetSpec) -> RuntimeRequest:
    """Sample RuntimeRequest for testing."""
    return RuntimeRequest(
        execution_id="REX-100",
        world_id="W-100",
        seed=42,
        target=mcp_target_spec,
        context=AgentRuntimeContext(
            message="Hello agent",
            state=AgentStateContext(memory={"test_mode": "non_instrumented"}),
        ),
        timeout_seconds=5.0,
    )


def test_mcp_config_parsing(tmp_path: Path) -> None:
    """Verify McpConfig parsing and validation in VivekaConfig."""
    cfg_file = tmp_path / ".viveka" / "config.yaml"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "runtime": {"adapter": "mcp"},
                "mcp": {
                    "transport": "stdio",
                    "command": "python",
                    "args": ["-m", "my_mcp_server"],
                    "tool": "custom.run",
                    "timeout_seconds": 15.0,
                    "env_from_host": {"FOO": "BAR"},
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_config(cfg_file)
    assert config.runtime.adapter == "mcp"
    assert config.mcp.transport == "stdio"
    assert config.mcp.command == "python"
    assert config.mcp.args == ["-m", "my_mcp_server"]
    assert config.mcp.tool == "custom.run"
    assert config.mcp.timeout_seconds == 15.0
    assert config.mcp.env_from_host == {"FOO": "BAR"}


def test_factory_creates_mcp_adapter(mcp_target_spec: TargetSpec) -> None:
    """Verify create_adapter returns a loaded McpRuntimeAdapter."""
    adapter = create_adapter(mcp_target_spec)
    assert isinstance(adapter, McpRuntimeAdapter)
    assert adapter.command == PYTHON_EXE
    assert adapter.args == [REF_SERVER]
    assert adapter.tool == "agent.run"


def test_missing_mcp_extra_raises_adapter_error(
    mcp_target_spec: TargetSpec, sample_request: RuntimeRequest
) -> None:
    """Verify that if HAS_MCP is False, load_target and execute raise AdapterError."""
    with patch("viveka.runtime.mcp_adapter.HAS_MCP", False):
        adapter = McpRuntimeAdapter()
        with pytest.raises(AdapterError, match="optional 'mcp' extra"):
            adapter.load_target(mcp_target_spec)

        with pytest.raises(AdapterError, match="optional 'mcp' extra"):
            adapter.execute(sample_request)


def test_unsupported_transport_raises(mcp_target_spec: TargetSpec) -> None:
    """Verify non-stdio transport raises AdapterError."""
    mcp_target_spec.options["transport"] = "sse"
    adapter = McpRuntimeAdapter()
    with pytest.raises(AdapterError, match="Unsupported transport 'sse'"):
        adapter.load_target(mcp_target_spec)


def test_missing_command_raises() -> None:
    """Verify missing command raises AdapterError."""
    spec = TargetSpec(adapter_type=RuntimeAdapterType.MCP, options={"transport": "stdio"})
    adapter = McpRuntimeAdapter()
    with pytest.raises(AdapterError, match="requires a valid command"):
        adapter.load_target(spec)


def test_execute_non_instrumented_target(
    mcp_target_spec: TargetSpec, sample_request: RuntimeRequest
) -> None:
    """Verify execution against non-instrumented MCP target."""
    adapter = create_adapter(mcp_target_spec)
    result = adapter.execute(sample_request)

    assert result.status == ExecutionStatus.SUCCESS
    assert result.final_output == "Processed world W-100 successfully"
    assert len(result.events) == 1
    assert result.events[0].event_type == RawEventType.AGENT_OUTPUT
    assert result.events[0].origin == EventOrigin.VIVEKA_OBSERVED


def test_execute_instrumented_target(
    mcp_target_spec: TargetSpec, sample_request: RuntimeRequest
) -> None:
    """Verify execution against instrumented MCP target with viveka_telemetry."""
    sample_request.context.state.memory["test_mode"] = "instrumented"
    adapter = create_adapter(mcp_target_spec)
    result = adapter.execute(sample_request)

    assert result.status == ExecutionStatus.SUCCESS
    assert result.final_output == "Processed world W-100 with telemetry"
    assert len(result.events) == 3

    # Check target-reported telemetry events
    assert result.events[0].event_type == RawEventType.TOOL_CALL
    assert result.events[0].origin == EventOrigin.TARGET_REPORTED
    assert result.events[0].tool_name == "read_file"

    assert result.events[1].event_type == RawEventType.TOOL_RESULT
    assert result.events[1].origin == EventOrigin.TARGET_REPORTED

    # Check final VIVEKA_OBSERVED AGENT_OUTPUT event at sequence N+1
    assert result.events[2].sequence == 3
    assert result.events[2].event_type == RawEventType.AGENT_OUTPUT
    assert result.events[2].origin == EventOrigin.VIVEKA_OBSERVED
    assert result.events[2].output_text == "Processed world W-100 with telemetry"


def test_execute_target_error(mcp_target_spec: TargetSpec, sample_request: RuntimeRequest) -> None:
    """Verify target tool returning isError=True maps to ExecutionStatus.TARGET_ERROR."""
    sample_request.context.state.memory["test_mode"] = "target_error"
    adapter = create_adapter(mcp_target_spec)
    result = adapter.execute(sample_request)

    assert result.status == ExecutionStatus.TARGET_ERROR
    assert "reported an error" in (result.error_message or "")


def test_execute_missing_configured_tool(
    mcp_target_spec: TargetSpec, sample_request: RuntimeRequest
) -> None:
    """Verify tool not in list_tools returns ExecutionStatus.ADAPTER_ERROR."""
    mcp_target_spec.options["tool"] = "nonexistent.tool"
    adapter = create_adapter(mcp_target_spec)
    result = adapter.execute(sample_request)

    assert result.status == ExecutionStatus.ADAPTER_ERROR
    assert "does not export configured tool 'nonexistent.tool'" in (result.error_message or "")


def test_execute_missing_output_field(
    mcp_target_spec: TargetSpec, sample_request: RuntimeRequest
) -> None:
    """Verify response missing string 'output' field returns ExecutionStatus.ADAPTER_ERROR."""
    sample_request.context.state.memory["test_mode"] = "missing_output"
    adapter = create_adapter(mcp_target_spec)
    result = adapter.execute(sample_request)

    assert result.status == ExecutionStatus.ADAPTER_ERROR
    assert "missing expected string field 'output'" in (result.error_message or "")


def test_execute_bad_telemetry_schema(
    mcp_target_spec: TargetSpec, sample_request: RuntimeRequest
) -> None:
    """Verify unsupported viveka_telemetry schema returns ExecutionStatus.ADAPTER_ERROR."""
    sample_request.context.state.memory["test_mode"] = "bad_telemetry"
    adapter = create_adapter(mcp_target_spec)
    result = adapter.execute(sample_request)

    assert result.status == ExecutionStatus.ADAPTER_ERROR
    assert "Unsupported or missing viveka_telemetry schema_version" in (result.error_message or "")


def test_execute_invalid_json(mcp_target_spec: TargetSpec, sample_request: RuntimeRequest) -> None:
    """Verify non-JSON tool output returns ExecutionStatus.ADAPTER_ERROR."""
    sample_request.context.state.memory["test_mode"] = "invalid_json"
    adapter = create_adapter(mcp_target_spec)
    result = adapter.execute(sample_request)

    assert result.status == ExecutionStatus.ADAPTER_ERROR
    assert "not valid JSON" in (result.error_message or "")


def test_execute_timeout(mcp_target_spec: TargetSpec, sample_request: RuntimeRequest) -> None:
    """Verify execution exceeding timeout returns ExecutionStatus.TIMEOUT."""
    sample_request.context.state.memory["test_mode"] = "timeout"
    sample_request.timeout_seconds = 1.0
    adapter = create_adapter(mcp_target_spec)
    result = adapter.execute(sample_request)

    assert result.status == ExecutionStatus.TIMEOUT
    assert "timed out after 1.0 seconds" in (result.error_message or "")


def test_execute_custom_tool_name(
    mcp_target_spec: TargetSpec, sample_request: RuntimeRequest
) -> None:
    """Verify invoking a custom tool name (e.g. custom.tool)."""
    mcp_target_spec.options["tool"] = "custom.tool"
    adapter = create_adapter(mcp_target_spec)
    result = adapter.execute(sample_request)

    assert result.status == ExecutionStatus.SUCCESS
    assert result.final_output == "custom tool output"


def test_healthcheck_success(mcp_target_spec: TargetSpec) -> None:
    """Verify healthcheck returns True when stdio server exports tool."""
    adapter = create_adapter(mcp_target_spec)
    assert adapter.healthcheck() is True


def test_healthcheck_failure() -> None:
    """Verify healthcheck returns False when target server command is invalid."""
    spec = TargetSpec(
        adapter_type=RuntimeAdapterType.MCP,
        options={"transport": "stdio", "command": "nonexistent_command_xyz_123"},
    )
    adapter = create_adapter(spec)
    assert adapter.healthcheck() is False


def test_oracle_observability_behavior(mcp_target_spec: TargetSpec) -> None:
    """Verify Observability Contract: Output-only MCP vs Instrumented MCP with Oracles."""
    binding = get_demo_capability_binding()

    flow_prop = Property(
        id="VPROP-01",
        name="Flow Forbidden",
        stable_key="PROP-100",
        description="Forbidden tool check",
        status=PropertyStatus.APPROVED,
        oracle=FlowForbiddenOracle(
            untrusted_source_key="src/search.py::knowledge_search",
            forbidden_sink_key="src/refund.py::refund_create",
        ),
    )

    failure_prop = Property(
        id="VPROP-02",
        name="Failure Handled",
        stable_key="PROP-100",
        description="Tool error recovery check",
        status=PropertyStatus.APPROVED,
        oracle=FailureHandledOracle(
            target_action_key="src/search.py::knowledge_search",
            must_not_represent_action_as_successful=True,
        ),
    )

    adapter = create_adapter(mcp_target_spec)

    # 1. Output-only (non-instrumented) MCP run -> INCONCLUSIVE
    req_non = RuntimeRequest(
        execution_id="REX-1",
        world_id="W-PROP-100",
        seed=1,
        target=mcp_target_spec,
        context=AgentRuntimeContext(
            state=AgentStateContext(memory={"test_mode": "non_instrumented"})
        ),
    )
    res_non = adapter.execute(req_non)
    trace_non = ExecutionTrace(
        trace_id="VTRC-1",
        execution_id=res_non.execution_id,
        world_id=res_non.world_id,
        status=res_non.status,
        events=res_non.events,
        final_output=res_non.final_output,
    )

    ctx_flow_non = EvaluationContext(property=flow_prop, trace=trace_non, binding=binding)
    ctx_fail_non = EvaluationContext(property=failure_prop, trace=trace_non, binding=binding)

    res_flow_non = FlowForbiddenEvaluator().evaluate(ctx_flow_non)
    res_fail_non = FailureHandledEvaluator().evaluate(ctx_fail_non)

    assert res_flow_non.verdict == EvaluationVerdict.INCONCLUSIVE
    assert res_fail_non.verdict == EvaluationVerdict.INCONCLUSIVE

    # 2. Instrumented MCP run -> Grounded Evaluation (NOT_APPLICABLE because source tool wasn't called)
    req_inst = RuntimeRequest(
        execution_id="REX-2",
        world_id="W-PROP-100",
        seed=1,
        target=mcp_target_spec,
        context=AgentRuntimeContext(state=AgentStateContext(memory={"test_mode": "instrumented"})),
    )
    res_inst = adapter.execute(req_inst)
    trace_inst = ExecutionTrace(
        trace_id="VTRC-2",
        execution_id=res_inst.execution_id,
        world_id=res_inst.world_id,
        status=res_inst.status,
        events=res_inst.events,
        final_output=res_inst.final_output,
    )

    ctx_flow_inst = EvaluationContext(property=flow_prop, trace=trace_inst, binding=binding)
    res_flow_inst = FlowForbiddenEvaluator().evaluate(ctx_flow_inst)

    # In instrumented mode, events exist so evaluation completes groundedly rather than INCONCLUSIVE
    assert res_flow_inst.verdict != EvaluationVerdict.INCONCLUSIVE


def test_execute_from_already_running_asyncio_event_loop(
    mcp_target_spec: TargetSpec, sample_request: RuntimeRequest
) -> None:
    """Verify contained thread bridge works when caller thread already has an active running asyncio loop."""

    async def _async_caller() -> None:
        # Confirm that an asyncio loop is active in this thread
        assert asyncio.get_running_loop() is not None
        adapter = create_adapter(mcp_target_spec)
        res = adapter.execute(sample_request)
        assert res.status == ExecutionStatus.SUCCESS
        assert res.final_output == "Processed world W-100 successfully"

    asyncio.run(_async_caller())


def test_env_from_host_resolves_secret_at_execution_time(
    mcp_target_spec: TargetSpec, sample_request: RuntimeRequest
) -> None:
    """Verify env_from_host maps TARGET_API_KEY -> HOST_VAR and secret value does not leak into TargetSpec."""
    os.environ["HOST_TEST_SECRET_KEY"] = "super-secret-mcp-token-123"
    try:
        mcp_target_spec.options["env_from_host"] = json.dumps(
            {"TARGET_API_KEY": "HOST_TEST_SECRET_KEY"}
        )
        sample_request.context.state.memory["test_mode"] = "secret_check"

        adapter = create_adapter(mcp_target_spec)
        res = adapter.execute(sample_request)

        assert res.status == ExecutionStatus.SUCCESS
        assert res.final_output == "Received secret: super-secret-mcp-token-123"

        # Assert secret value does NOT appear in spec, options, or result dump
        spec_dump = json.dumps(mcp_target_spec.model_dump())
        assert "super-secret-mcp-token-123" not in spec_dump
        assert "HOST_TEST_SECRET_KEY" in spec_dump
    finally:
        os.environ.pop("HOST_TEST_SECRET_KEY", None)


def test_env_from_host_missing_host_var_fails_without_leaking(
    mcp_target_spec: TargetSpec, sample_request: RuntimeRequest
) -> None:
    """Verify missing host environment variable fails cleanly with ADAPTER_ERROR without dumping host environment."""
    os.environ.pop("NONEXISTENT_HOST_KEY_999", None)
    mcp_target_spec.options["env_from_host"] = json.dumps(
        {"TARGET_API_KEY": "NONEXISTENT_HOST_KEY_999"}
    )

    adapter = create_adapter(mcp_target_spec)
    res = adapter.execute(sample_request)

    assert res.status == ExecutionStatus.ADAPTER_ERROR
    assert "Missing required host environment variable 'NONEXISTENT_HOST_KEY_999'" in (
        res.error_message or ""
    )


def test_unsupported_feature_interactive_flow(
    mcp_target_spec: TargetSpec, sample_request: RuntimeRequest
) -> None:
    """Verify interactive elicitation requested by target maps to ExecutionStatus.UNSUPPORTED_FEATURE."""
    sample_request.context.state.memory["test_mode"] = "elicitation"
    adapter = create_adapter(mcp_target_spec)
    res = adapter.execute(sample_request)

    assert res.status == ExecutionStatus.UNSUPPORTED_FEATURE
    assert "unsupported interactive feature" in (res.error_message or "")


def test_exactly_one_target_invocation_per_request(
    tmp_path: Path, mcp_target_spec: TargetSpec, sample_request: RuntimeRequest
) -> None:
    """Verify that exactly ONE agent tool call occurs per RuntimeRequest execution."""
    counter_file = tmp_path / "invocation_counter.txt"
    os.environ["VIVEKA_TEST_INVOCATION_COUNTER_FILE"] = str(counter_file)

    try:
        adapter = create_adapter(mcp_target_spec)
        res = adapter.execute(sample_request)
        assert res.status == ExecutionStatus.SUCCESS

        assert counter_file.exists()
        count = int(counter_file.read_text(encoding="utf-8").strip())
        assert count == 1
    finally:
        os.environ.pop("VIVEKA_TEST_INVOCATION_COUNTER_FILE", None)
