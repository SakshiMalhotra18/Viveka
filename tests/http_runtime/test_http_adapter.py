"""
Comprehensive tests for HttpJsonRuntimeAdapter, TargetSpec, and factory in Phase 13.
"""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from tests.http_runtime.reference_server import ReferenceHTTPServer

from viveka.diagnosis.models import DiagnosisEvidence
from viveka.evaluation.models import EvaluationEvidence
from viveka.runtime.factory import create_adapter
from viveka.runtime.http_adapter import HttpJsonRuntimeAdapter, is_local_target_endpoint
from viveka.runtime.models import AgentRuntimeContext, RawEvent, RuntimeRequest, TargetSpec
from viveka.runtime.python_adapter import AdapterError
from viveka.runtime.vocabulary import EventOrigin, ExecutionStatus, RawEventType, RuntimeAdapterType


@pytest.fixture
def http_server() -> Generator[ReferenceHTTPServer, None, None]:
    """Start and yield an offline reference HTTP server fixture."""
    server = ReferenceHTTPServer()
    server.start()
    yield server
    server.stop()


class TestLocalEndpointClassification:
    def test_localhost_and_loopback_accepted(self) -> None:
        assert is_local_target_endpoint("http://localhost:8000/agent") is True
        assert is_local_target_endpoint("http://127.0.0.1:8080/agent") is True
        assert is_local_target_endpoint("http://127.0.0.2:8080/agent") is True
        assert is_local_target_endpoint("http://[::1]:8000/agent") is True

    def test_wildcard_0000_rejected(self) -> None:
        assert is_local_target_endpoint("http://0.0.0.0:8000/agent") is False
        assert is_local_target_endpoint("http://[::]:8000/agent") is False

    def test_remote_host_is_not_local(self) -> None:
        assert is_local_target_endpoint("http://example.com/agent") is False
        assert is_local_target_endpoint("https://api.openai.com/v1") is False
        assert is_local_target_endpoint("http://192.168.1.100/agent") is False


class TestTargetSpecAndValidation:
    def test_endpoint_stored_on_endpoint_field(self) -> None:
        spec = TargetSpec(
            adapter_type=RuntimeAdapterType.HTTP,
            endpoint="http://localhost:8000/agent",
        )
        assert spec.endpoint == "http://localhost:8000/agent"
        assert spec.import_path is None

    def test_missing_endpoint_raises(self) -> None:
        adapter = HttpJsonRuntimeAdapter()
        spec = TargetSpec(adapter_type=RuntimeAdapterType.HTTP)
        with pytest.raises(AdapterError, match="requires a valid endpoint"):
            adapter.load_target(spec)

    def test_unsupported_scheme_raises(self) -> None:
        adapter = HttpJsonRuntimeAdapter()
        spec = TargetSpec(adapter_type=RuntimeAdapterType.HTTP, endpoint="file:///tmp/agent")
        with pytest.raises(AdapterError, match="Unsupported URL scheme"):
            adapter.load_target(spec)

    def test_destination_0000_rejected(self) -> None:
        adapter = HttpJsonRuntimeAdapter()
        spec = TargetSpec(
            adapter_type=RuntimeAdapterType.HTTP, endpoint="http://0.0.0.0:8000/agent"
        )
        with pytest.raises(AdapterError, match="invalid as an execution target address"):
            adapter.load_target(spec)

    def test_remote_host_blocked_without_opt_in(self) -> None:
        adapter = HttpJsonRuntimeAdapter()
        spec = TargetSpec(
            adapter_type=RuntimeAdapterType.HTTP,
            endpoint="http://remote.host.com/agent",
            options={"allow_remote_target": "false"},
        )
        with pytest.raises(AdapterError, match="resolves to a remote host"):
            adapter.load_target(spec)

    def test_remote_host_allowed_with_explicit_opt_in(self) -> None:
        adapter = HttpJsonRuntimeAdapter()
        spec = TargetSpec(
            adapter_type=RuntimeAdapterType.HTTP,
            endpoint="http://remote.host.com/agent",
            options={"allow_remote_target": "true"},
        )
        adapter.load_target(spec)
        assert adapter.endpoint == "http://remote.host.com/agent"


class TestHttpStatusMapping:
    @pytest.mark.parametrize(
        ("path", "expected_status_code"),
        [
            ("/agent/redirect_302", "302"),
            ("/agent/error_400", "400"),
            ("/agent/error_401", "401"),
            ("/agent/error_404", "404"),
            ("/agent/error_429", "429"),
            ("/agent/error_500", "500"),
        ],
    )
    def test_valid_non_2xx_maps_to_target_error(
        self, http_server: ReferenceHTTPServer, path: str, expected_status_code: str
    ) -> None:
        spec = TargetSpec(
            adapter_type=RuntimeAdapterType.HTTP,
            endpoint=f"http://{http_server.host}:{http_server.port}{path}",
        )
        adapter = create_adapter(spec)
        req = RuntimeRequest(
            execution_id="VRUN-01J8STAT",
            world_id="VWORLD-01J8STAT",
            target=spec,
            context=AgentRuntimeContext(message="Status test"),
        )
        res = adapter.execute(req)
        assert res.status == ExecutionStatus.TARGET_ERROR
        assert expected_status_code in res.error_message

    def test_connection_failure_maps_to_adapter_error(self) -> None:
        # Port 59999 has no listener
        spec = TargetSpec(
            adapter_type=RuntimeAdapterType.HTTP,
            endpoint="http://127.0.0.1:59999/agent",
        )
        adapter = create_adapter(spec)
        req = RuntimeRequest(
            execution_id="VRUN-01J8CONN",
            world_id="VWORLD-01J8CONN",
            target=spec,
            context=AgentRuntimeContext(message="Connection test"),
        )
        res = adapter.execute(req)
        assert res.status == ExecutionStatus.ADAPTER_ERROR
        assert "connection failed" in res.error_message.lower()

    def test_timeout_maps_to_timeout(self, http_server: ReferenceHTTPServer) -> None:
        spec = TargetSpec(
            adapter_type=RuntimeAdapterType.HTTP,
            endpoint=f"http://{http_server.host}:{http_server.port}/agent/slow",
            options={"timeout_seconds": "0.1"},
        )
        adapter = create_adapter(spec)
        req = RuntimeRequest(
            execution_id="VRUN-01J8TIME",
            world_id="VWORLD-01J8TIME",
            target=spec,
            context=AgentRuntimeContext(message="Timeout test"),
            timeout_seconds=0.1,
        )
        res = adapter.execute(req)
        assert res.status == ExecutionStatus.TIMEOUT
        assert "timed out" in res.error_message.lower()


class TestRedirectsDisabled:
    def test_redirects_are_not_followed(self, http_server: ReferenceHTTPServer) -> None:
        spec = TargetSpec(
            adapter_type=RuntimeAdapterType.HTTP,
            endpoint=f"http://{http_server.host}:{http_server.port}/agent/redirect_302",
        )
        adapter = create_adapter(spec)
        req = RuntimeRequest(
            execution_id="VRUN-01J8REDIR",
            world_id="VWORLD-01J8REDIR",
            target=spec,
            context=AgentRuntimeContext(message="Redirect test"),
        )
        res = adapter.execute(req)
        # 302 must NOT be followed; surfaced as TARGET_ERROR
        assert res.status == ExecutionStatus.TARGET_ERROR
        assert "302" in res.error_message


class TestResponseOutputContract:
    def test_canonical_output_field_parsed(self, http_server: ReferenceHTTPServer) -> None:
        spec = TargetSpec(
            adapter_type=RuntimeAdapterType.HTTP,
            endpoint=http_server.endpoint_url,
        )
        adapter = create_adapter(spec)
        req = RuntimeRequest(
            execution_id="VRUN-01J8OK",
            world_id="VWORLD-01J8OK",
            target=spec,
            context=AgentRuntimeContext(message="Hello output"),
        )
        res = adapter.execute(req)
        assert res.status == ExecutionStatus.SUCCESS
        assert res.final_output.startswith("Processed message: 'Hello output'")

    def test_custom_output_field_configured(self, http_server: ReferenceHTTPServer) -> None:
        spec = TargetSpec(
            adapter_type=RuntimeAdapterType.HTTP,
            endpoint=f"http://{http_server.host}:{http_server.port}/agent/custom_output_field",
            options={"response_output_field": "custom_text"},
        )
        adapter = create_adapter(spec)
        req = RuntimeRequest(
            execution_id="VRUN-01J8CUST",
            world_id="VWORLD-01J8CUST",
            target=spec,
            context=AgentRuntimeContext(message="Custom field"),
        )
        res = adapter.execute(req)
        assert res.status == ExecutionStatus.SUCCESS
        assert res.final_output == "Processed custom field"

    def test_missing_output_field_fails_with_adapter_error(
        self, http_server: ReferenceHTTPServer
    ) -> None:
        spec = TargetSpec(
            adapter_type=RuntimeAdapterType.HTTP,
            endpoint=f"http://{http_server.host}:{http_server.port}/agent/missing_output_field",
        )
        adapter = create_adapter(spec)
        req = RuntimeRequest(
            execution_id="VRUN-01J8MISS",
            world_id="VWORLD-01J8MISS",
            target=spec,
            context=AgentRuntimeContext(message="Missing field"),
        )
        res = adapter.execute(req)
        assert res.status == ExecutionStatus.ADAPTER_ERROR
        assert "missing expected string field 'output'" in res.error_message

    def test_no_response_key_guessing(self, http_server: ReferenceHTTPServer) -> None:
        # Verify that if 'output' is missing, adapter does NOT fall back to guessing other keys
        spec = TargetSpec(
            adapter_type=RuntimeAdapterType.HTTP,
            endpoint=f"http://{http_server.host}:{http_server.port}/agent/missing_output_field",
        )
        adapter = create_adapter(spec)
        req = RuntimeRequest(
            execution_id="VRUN-01J8NOGUESS",
            world_id="VWORLD-01J8NOGUESS",
            target=spec,
            context=AgentRuntimeContext(message="No guessing"),
        )
        res = adapter.execute(req)
        assert res.status == ExecutionStatus.ADAPTER_ERROR


class TestVersionedInstrumentationContract:
    def test_valid_telemetry_parsed_and_ordered(self, http_server: ReferenceHTTPServer) -> None:
        spec = TargetSpec(
            adapter_type=RuntimeAdapterType.HTTP,
            endpoint=f"http://{http_server.host}:{http_server.port}/agent/instrumented",
        )
        adapter = create_adapter(spec)
        req = RuntimeRequest(
            execution_id="VRUN-01J8INST",
            world_id="VWORLD-01J8INST",
            target=spec,
            context=AgentRuntimeContext(message="Instrumented test"),
        )
        res = adapter.execute(req)
        assert res.status == ExecutionStatus.SUCCESS
        # 2 target-reported events + 1 final VIVEKA_OBSERVED AGENT_OUTPUT = 3 total events
        assert len(res.events) == 3

        # Verify TARGET_REPORTED origin and ordering
        assert res.events[0].event_type == RawEventType.TOOL_CALL
        assert res.events[0].origin == EventOrigin.TARGET_REPORTED
        assert res.events[0].sequence == 1
        assert res.events[0].call_id == "call-101"

        assert res.events[1].event_type == RawEventType.TOOL_RESULT
        assert res.events[1].origin == EventOrigin.TARGET_REPORTED
        assert res.events[1].sequence == 2

        # Verify final AGENT_OUTPUT follows at sequence 3 with VIVEKA_OBSERVED origin
        assert res.events[2].event_type == RawEventType.AGENT_OUTPUT
        assert res.events[2].origin == EventOrigin.VIVEKA_OBSERVED
        assert res.events[2].sequence == 3

    def test_unsupported_schema_version_fails(self, http_server: ReferenceHTTPServer) -> None:
        spec = TargetSpec(
            adapter_type=RuntimeAdapterType.HTTP,
            endpoint=f"http://{http_server.host}:{http_server.port}/agent/instrumented_unsupported_version",
        )
        adapter = create_adapter(spec)
        req = RuntimeRequest(
            execution_id="VRUN-01J8BADVER",
            world_id="VWORLD-01J8BADVER",
            target=spec,
            context=AgentRuntimeContext(message="Bad ver"),
        )
        res = adapter.execute(req)
        assert res.status == ExecutionStatus.ADAPTER_ERROR
        assert "schema_version" in res.error_message

    def test_incomplete_telemetry_fails(self, http_server: ReferenceHTTPServer) -> None:
        spec = TargetSpec(
            adapter_type=RuntimeAdapterType.HTTP,
            endpoint=f"http://{http_server.host}:{http_server.port}/agent/instrumented_incomplete",
        )
        adapter = create_adapter(spec)
        req = RuntimeRequest(
            execution_id="VRUN-01J8INCOMP",
            world_id="VWORLD-01J8INCOMP",
            target=spec,
            context=AgentRuntimeContext(message="Incomplete"),
        )
        res = adapter.execute(req)
        assert res.status == ExecutionStatus.ADAPTER_ERROR
        assert "complete flag is not true" in res.error_message

    def test_invalid_event_type_fails(self, http_server: ReferenceHTTPServer) -> None:
        spec = TargetSpec(
            adapter_type=RuntimeAdapterType.HTTP,
            endpoint=f"http://{http_server.host}:{http_server.port}/agent/instrumented_invalid_event",
        )
        adapter = create_adapter(spec)
        req = RuntimeRequest(
            execution_id="VRUN-01J8BADEV",
            world_id="VWORLD-01J8BADEV",
            target=spec,
            context=AgentRuntimeContext(message="Bad event"),
        )
        res = adapter.execute(req)
        assert res.status == ExecutionStatus.ADAPTER_ERROR
        assert "Invalid event_type" in res.error_message


class TestEventProvenanceSurvives:
    def test_python_events_default_to_viveka_observed(self) -> None:
        evt = RawEvent(sequence=1, event_id="E1", event_type=RawEventType.AGENT_OUTPUT)
        assert evt.origin == EventOrigin.VIVEKA_OBSERVED

    def test_provenance_survives_to_evaluation_and_diagnosis_evidence(self) -> None:
        target_evt = RawEvent(
            sequence=1,
            event_id="E-T1",
            event_type=RawEventType.TOOL_CALL,
            origin=EventOrigin.TARGET_REPORTED,
        )
        eval_ev = EvaluationEvidence(
            event_id=target_evt.event_id,
            sequence=target_evt.sequence,
            event_type=target_evt.event_type,
            event_origin=target_evt.origin,
            description="Target tool call",
        )
        assert eval_ev.event_origin == EventOrigin.TARGET_REPORTED

        diag_ev = DiagnosisEvidence(
            event_id=eval_ev.event_id,
            sequence=eval_ev.sequence,
            event_type=eval_ev.event_type,
            event_origin=eval_ev.event_origin,
            description=eval_ev.description,
        )
        assert diag_ev.event_origin == EventOrigin.TARGET_REPORTED


class TestSecretSanitization:
    def test_secret_token_not_persisted_in_result(self, http_server: ReferenceHTTPServer) -> None:
        os.environ["SECRET_ENV_TOKEN"] = "my-secret-bearer-token-999"
        try:
            spec = TargetSpec(
                adapter_type=RuntimeAdapterType.HTTP,
                endpoint=http_server.endpoint_url,
                options={"auth_header_env": "SECRET_ENV_TOKEN"},
            )
            adapter = create_adapter(spec)
            req = RuntimeRequest(
                execution_id="VRUN-01J8SEC",
                world_id="VWORLD-01J8SEC",
                target=spec,
                context=AgentRuntimeContext(message="Secret test"),
            )
            res = adapter.execute(req)
            assert res.status == ExecutionStatus.SUCCESS
            dumped = res.model_dump(mode="json")
            assert "my-secret-bearer-token-999" not in str(dumped)
        finally:
            os.environ.pop("SECRET_ENV_TOKEN", None)
