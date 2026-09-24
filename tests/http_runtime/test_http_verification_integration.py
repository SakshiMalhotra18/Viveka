"""
Integration test for VIVEKA Phase 13 HTTP runtime integration and output-only oracle semantics.

Verifies end-to-end property verification, output-only INCONCLUSIVE oracle semantics,
instrumented telemetry evaluation, and VerificationEngine target resolution.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from tests.http_runtime.reference_server import ReferenceHTTPServer

from viveka.core.config import VivekaConfig, write_default_config
from viveka.evaluation.models import ReproductionPolicy, RuntimeCapabilityBinding
from viveka.properties.models import FailureHandledOracle, FlowForbiddenOracle, Property
from viveka.properties.store import PropertyStore
from viveka.properties.vocabulary import PropertyStatus
from viveka.runtime.models import TargetSpec
from viveka.runtime.vocabulary import RuntimeAdapterType
from viveka.verification.engine import VerificationEngine
from viveka.verification.vocabulary import PropertyVerificationStatus, VerificationOutcome


@pytest.fixture
def http_server() -> Generator[ReferenceHTTPServer, None, None]:
    """Start and yield reference HTTP server fixture."""
    server = ReferenceHTTPServer()
    server.start()
    yield server
    server.stop()


def test_http_verification_engine_resolution(
    tmp_path: Path, http_server: ReferenceHTTPServer
) -> None:
    """Verify VerificationEngine resolves HTTP adapter target from project configuration."""
    cfg_path = tmp_path / ".viveka" / "config.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    write_default_config(cfg_path)

    config = VivekaConfig(version=1)
    config.runtime.adapter = "http"
    config.interface.endpoint = http_server.endpoint_url
    config.reasoning.mode = "none"  # reasoning.mode=none remains independent
    config.capability_bindings = {
        "knowledge_search": "knowledge.search",
        "refund_create": "refund.create",
    }

    prop_store = PropertyStore(tmp_path)
    prop = Property(
        id="VPROP-01J8RESOLVE",
        stable_key="prop_resolve_test",
        name="Flow Forbidden Property",
        description="Flow forbidden property",
        status=PropertyStatus.APPROVED,
        oracle=FlowForbiddenOracle(
            untrusted_source_key="knowledge_search",
            forbidden_sink_key="refund_create",
        ),
    )
    prop_store.save(prop)

    engine = VerificationEngine(project_root=tmp_path, config=config)
    target, binding = engine.resolve_target_and_binding()

    assert target.adapter_type == RuntimeAdapterType.HTTP
    assert target.endpoint == http_server.endpoint_url
    assert binding is not None
    assert binding.bindings == config.capability_bindings


def test_output_only_flow_forbidden_oracle_returns_inconclusive(
    tmp_path: Path, http_server: ReferenceHTTPServer
) -> None:
    """Output-only HTTP boundary produces INCONCLUSIVE for FlowForbiddenOracle due to missing tool telemetry."""
    prop_store = PropertyStore(tmp_path)
    prop = Property(
        id="VPROP-01J8FLOWINC",
        stable_key="prop_flow_inc",
        name="Forbidden Tool Flow",
        description="Forbidden flow from search to refund",
        status=PropertyStatus.APPROVED,
        oracle=FlowForbiddenOracle(
            untrusted_source_key="knowledge_search",
            forbidden_sink_key="refund_create",
        ),
    )
    prop_store.save(prop)

    engine = VerificationEngine(project_root=tmp_path)
    result = engine.verify(
        property_filter=prop.id,
        policy=ReproductionPolicy(runs=2, minimum_violations=1),
        target_spec=TargetSpec(
            adapter_type=RuntimeAdapterType.HTTP,
            endpoint=http_server.endpoint_url,
        ),
        binding=RuntimeCapabilityBinding(
            bindings={
                "knowledge_search": "knowledge.search",
                "refund_create": "refund.create",
            }
        ),
    )

    assert result.outcome == VerificationOutcome.NO_REPRODUCED_VIOLATIONS
    assert len(result.property_results) == 1
    prop_res = result.property_results[0]
    # Locked requirement: Output-only HTTP FlowForbidden -> INCONCLUSIVE
    assert prop_res.status == PropertyVerificationStatus.INCONCLUSIVE


def test_output_only_failure_handled_oracle_returns_inconclusive(
    tmp_path: Path, http_server: ReferenceHTTPServer
) -> None:
    """Output-only HTTP boundary produces INCONCLUSIVE for FailureHandledOracle due to missing tool telemetry."""
    prop_store = PropertyStore(tmp_path)
    prop = Property(
        id="VPROP-01J8FAILINC",
        stable_key="prop_fail_inc",
        name="Tool Failure Handling",
        description="Tool failure handling invariant",
        status=PropertyStatus.APPROVED,
        oracle=FailureHandledOracle(
            target_action_key="knowledge_search",
            must_not_represent_action_as_successful=True,
        ),
    )
    prop_store.save(prop)

    engine = VerificationEngine(project_root=tmp_path)
    result = engine.verify(
        property_filter=prop.id,
        policy=ReproductionPolicy(runs=2, minimum_violations=1),
        target_spec=TargetSpec(
            adapter_type=RuntimeAdapterType.HTTP,
            endpoint=http_server.endpoint_url,
        ),
        binding=RuntimeCapabilityBinding(bindings={"knowledge_search": "knowledge.search"}),
    )

    assert result.outcome == VerificationOutcome.NO_REPRODUCED_VIOLATIONS
    assert len(result.property_results) == 1
    prop_res = result.property_results[0]
    # Locked requirement: Output-only HTTP FailureHandled -> INCONCLUSIVE
    assert prop_res.status == PropertyVerificationStatus.INCONCLUSIVE


def test_instrumented_http_telemetry_evaluates_flow_forbidden(
    tmp_path: Path, http_server: ReferenceHTTPServer
) -> None:
    """Instrumented HTTP target with reported telemetry allows FlowForbidden evaluation."""
    prop_store = PropertyStore(tmp_path)
    prop = Property(
        id="VPROP-01J8INSTFLOW",
        stable_key="prop_inst_flow",
        name="Instrumented Forbidden Flow",
        description="Forbidden flow evaluated on instrumented target",
        status=PropertyStatus.APPROVED,
        oracle=FlowForbiddenOracle(
            untrusted_source_key="src/search.py::knowledge_search",
            forbidden_sink_key="src/refund.py::refund_create",
        ),
    )
    prop_store.save(prop)

    instrumented_endpoint = f"http://{http_server.host}:{http_server.port}/agent/instrumented"
    engine = VerificationEngine(project_root=tmp_path)
    result = engine.verify(
        property_filter=prop.id,
        policy=ReproductionPolicy(runs=2, minimum_violations=1),
        target_spec=TargetSpec(
            adapter_type=RuntimeAdapterType.HTTP,
            endpoint=instrumented_endpoint,
        ),
        binding=RuntimeCapabilityBinding(
            bindings={
                "src/search.py::knowledge_search": "knowledge_search",
                "src/refund.py::refund_create": "refund_create",
            }
        ),
    )

    assert result.outcome == VerificationOutcome.NO_REPRODUCED_VIOLATIONS
    assert len(result.property_results) == 1
    prop_res = result.property_results[0]
    # Instrumented target reported knowledge_search but no refund_create -> NO_REPRODUCED_VIOLATION
    assert prop_res.status == PropertyVerificationStatus.NO_REPRODUCED_VIOLATION
