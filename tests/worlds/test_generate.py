"""Tests for Phase 6 WorldGenerator."""

from datetime import UTC, datetime

from viveka.core.ids import new_id
from viveka.properties.models import (
    AppliesWhen,
    FailureHandledOracle,
    FlowForbiddenOracle,
    Property,
)
from viveka.properties.vocabulary import PropertySource, PropertyStatus
from viveka.worlds.generate import WorldGenerator
from viveka.worlds.vocabulary import ToolBehavior


def test_generate_worlds_for_flow_forbidden():
    prop = Property(
        id=new_id("VPROP"),
        stable_key="test:rule:flow",
        name="retrieved-content-cannot-authorize-refund",
        description="Forbidden flow test property",
        status=PropertyStatus.APPROVED,
        source=PropertySource.RULE_DERIVED,
        applies_when=AppliesWhen(
            source_capability_keys=["src/read.py::search"],
            sink_capability_keys=["src/pay.py::refund"],
        ),
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="src/read.py::search",
            forbidden_sink_key="src/pay.py::refund",
        ),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    gen = WorldGenerator(seed=12345)
    worlds = gen.generate_worlds([prop], max_worlds_per_property=5)

    assert len(worlds) == 5
    for w in worlds:
        assert w.property_id == prop.id
        assert w.property_stable_key == prop.stable_key


def test_generate_worlds_for_failure_handled():
    prop = Property(
        id=new_id("VPROP"),
        stable_key="test:rule:fail",
        name="tool-failure-must-not-claim-success",
        description="Failure handled test property",
        status=PropertyStatus.APPROVED,
        source=PropertySource.RULE_DERIVED,
        oracle=FailureHandledOracle(
            evaluator_kind="failure_handled",
            target_action_key="src/tools.py::delete_account",
        ),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    gen = WorldGenerator(seed=54321)
    worlds = gen.generate_worlds([prop], max_worlds_per_property=4)

    assert len(worlds) == 4
    # Check baseline has tool failing
    baseline = worlds[0]
    assert "delete_account" in baseline.tools
    assert baseline.tools["delete_account"].behavior == ToolBehavior.EXCEPTION


def test_generate_worlds_seed_reproducibility():
    prop = Property(
        id=new_id("VPROP"),
        stable_key="test:rule:repro",
        name="reproducibility-test",
        description="Seed reproducibility check",
        status=PropertyStatus.APPROVED,
        source=PropertySource.RULE_DERIVED,
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="src/in.py::read",
            forbidden_sink_key="src/out.py::write",
        ),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    gen1 = WorldGenerator(seed=9999)
    worlds1 = gen1.generate_worlds([prop], max_worlds_per_property=3)

    gen2 = WorldGenerator(seed=9999)
    worlds2 = gen2.generate_worlds([prop], max_worlds_per_property=3)

    assert len(worlds1) == len(worlds2) == 3
    for w1, w2 in zip(worlds1, worlds2, strict=True):
        assert w1.seed == w2.seed
        assert w1.input.message == w2.input.message
        assert len(w1.mutations) == len(w2.mutations)
