"""Tests for viveka.properties.models — discriminated union oracles, evidence refs, and catalog."""

from __future__ import annotations

from datetime import UTC, datetime

import yaml

from viveka.properties.models import (
    AppliesWhen,
    FailureHandledOracle,
    FlowForbiddenOracle,
    Property,
    PropertyCatalog,
    PropertyEvidenceRef,
    PropertyRevisionRecord,
)
from viveka.properties.vocabulary import (
    PropertyEvidenceType,
    PropertySource,
    PropertyStatus,
)


def _sample_flow_property(
    prop_id: str = "VPROP-01flow",
    status: PropertyStatus = PropertyStatus.CANDIDATE,
) -> Property:
    return Property(
        id=prop_id,
        stable_key="prop-rule-ret-fin-001:forbidden_flow:src/tools.py::search->src/tools.py::refund",
        name="retrieved-content-cannot-authorize-refund",
        description="Content returned by retrieval capabilities must not independently authorize a financial action.",
        status=status,
        source=PropertySource.RULE_DERIVED,
        confidence="high",
        applies_when=AppliesWhen(
            source_capability_keys=["src/tools.py::search"],
            sink_capability_keys=["src/tools.py::refund"],
            source_symbols=["search"],
            sink_symbols=["refund"],
        ),
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="src/tools.py::search",
            forbidden_sink_key="src/tools.py::refund",
            allowed_exceptions=["explicit_user_authorization"],
        ),
        evidence=[
            PropertyEvidenceRef(
                evidence_type=PropertyEvidenceType.CAPABILITY,
                source_id="src/tools.py::search",
                description="Retrieval source",
                file_path="src/tools.py",
                line=12,
            ),
            PropertyEvidenceRef(
                evidence_type=PropertyEvidenceType.GRAPH_PATH,
                source_id="ep:main->tools",
                description="Graph reachability from main",
                file_path="src/agent.py",
                line=None,  # Optional line test
            ),
        ],
        rationale="Sample rationale.",
        rule_id="PROP-RULE-RET-FIN-001",
    )


def _sample_failure_property(
    prop_id: str = "VPROP-02fail",
    status: PropertyStatus = PropertyStatus.CANDIDATE,
) -> Property:
    return Property(
        id=prop_id,
        stable_key="prop-rule-fail-silent-001:must_handle_failure:src/tools.py::refund",
        name="tool-failure-must-not-claim-success-refund",
        description="If a tool fails, the agent must not claim the action succeeded.",
        status=status,
        source=PropertySource.RULE_DERIVED,
        confidence="high",
        applies_when=AppliesWhen(
            sink_capability_keys=["src/tools.py::refund"],
            sink_symbols=["refund"],
        ),
        oracle=FailureHandledOracle(
            evaluator_kind="failure_handled",
            target_action_key="src/tools.py::refund",
            must_not_represent_action_as_successful=True,
        ),
        evidence=[
            PropertyEvidenceRef(
                evidence_type=PropertyEvidenceType.CAPABILITY,
                source_id="src/tools.py::refund",
                description="Exposed mutating tool",
                file_path="src/tools.py",
                line=25,
            )
        ],
        rule_id="PROP-RULE-FAIL-SILENT-001",
    )


class TestPropertyModels:
    def test_flow_forbidden_oracle_discriminated_union(self) -> None:
        prop = _sample_flow_property()
        data = prop.model_dump(mode="json")
        reloaded = Property.model_validate(data)

        assert isinstance(reloaded.oracle, FlowForbiddenOracle)
        assert reloaded.oracle.evaluator_kind == "flow_forbidden"
        assert reloaded.oracle.untrusted_source_key == "src/tools.py::search"
        assert reloaded.oracle.forbidden_sink_key == "src/tools.py::refund"

    def test_failure_handled_oracle_discriminated_union(self) -> None:
        prop = _sample_failure_property()
        data = prop.model_dump(mode="json")
        reloaded = Property.model_validate(data)

        assert isinstance(reloaded.oracle, FailureHandledOracle)
        assert reloaded.oracle.evaluator_kind == "failure_handled"
        assert reloaded.oracle.must_not_represent_action_as_successful is True
        assert not hasattr(reloaded.oracle, "forbidden_claim_patterns")

    def test_evidence_ref_with_and_without_line(self) -> None:
        prop = _sample_flow_property()
        assert prop.evidence[0].line == 12
        assert prop.evidence[1].line is None
        assert prop.evidence[0].evidence_type == PropertyEvidenceType.CAPABILITY
        assert prop.evidence[1].evidence_type == PropertyEvidenceType.GRAPH_PATH

    def test_revision_record_timezone_aware(self) -> None:
        now = datetime.now(UTC)
        rec = PropertyRevisionRecord(
            revision=2,
            status=PropertyStatus.APPROVED,
            timestamp=now,
            reason="Approved by reviewer",
        )
        assert rec.timestamp.tzinfo is not None
        assert rec.revision == 2

    def test_property_yaml_roundtrip(self) -> None:
        prop = _sample_flow_property()
        dumped = prop.model_dump(mode="json")
        yaml_text = yaml.safe_dump(dumped)
        loaded_dict = yaml.safe_load(yaml_text)
        reloaded = Property.model_validate(loaded_dict)

        assert reloaded.id == prop.id
        assert reloaded.stable_key == prop.stable_key
        assert isinstance(reloaded.oracle, FlowForbiddenOracle)


class TestPropertyCatalog:
    def test_catalog_query_helpers(self) -> None:
        p1 = _sample_flow_property("VPROP-01", PropertyStatus.CANDIDATE)
        p2 = _sample_failure_property("VPROP-02", PropertyStatus.APPROVED)
        p3 = _sample_flow_property("VPROP-03", PropertyStatus.REJECTED)

        catalog = PropertyCatalog(properties=[p1, p2, p3])

        assert len(catalog.candidates) == 1
        assert catalog.candidates[0].id == "VPROP-01"

        assert len(catalog.approved) == 1
        assert catalog.approved[0].id == "VPROP-02"

        assert len(catalog.rejected) == 1
        assert catalog.rejected[0].id == "VPROP-03"

        assert catalog.by_id("VPROP-02") == p2
        assert catalog.by_stable_key(p1.stable_key) == p1
        assert catalog.by_id("nonexistent") is None
