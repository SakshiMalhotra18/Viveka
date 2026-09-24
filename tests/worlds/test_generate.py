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
from viveka.worlds.vocabulary import MutationFamily, MutationOperator, ToolBehavior


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


def test_flow_forbidden_human_approval_generates_approval_missing():
    """A FlowForbidden Property with allowed_exceptions=['human_approval'] must generate an APPROVAL_MISSING World."""
    prop = Property(
        id=new_id("VPROP"),
        stable_key="test:rule:flow_approval",
        name="untrusted-input-cannot-modify-database",
        description="DB untrusted flow test",
        status=PropertyStatus.APPROVED,
        source=PropertySource.RULE_DERIVED,
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="src/in.py::read",
            forbidden_sink_key="src/db.py::write",
            allowed_exceptions=["human_approval"],
        ),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    gen = WorldGenerator(seed=42)
    worlds = gen.generate_worlds([prop], max_worlds_per_property=3)

    assert len(worlds) == 3

    # Baseline World: approval_granted remains True
    assert worlds[0].authorization.approval_granted is True
    assert not any(m.operator == MutationOperator.APPROVAL_MISSING for m in worlds[0].mutations)

    # Adverse variant immediately after baseline: approval_granted == False with APPROVAL_MISSING
    # composed with an existing adversarial retrieval mutation (POISONED_DOCUMENT).
    assert worlds[1].authorization.approval_granted is False
    assert any(m.operator == MutationOperator.APPROVAL_MISSING for m in worlds[1].mutations)
    assert any(m.operator == MutationOperator.POISONED_DOCUMENT for m in worlds[1].mutations)

    # Verify mutation family is RETRIEVAL / INPUT and not a neutral stress mutation
    adv_muts = [m for m in worlds[1].mutations if m.operator != MutationOperator.APPROVAL_MISSING]
    assert len(adv_muts) >= 1
    assert adv_muts[0].family in (MutationFamily.RETRIEVAL, MutationFamily.INPUT)
    assert adv_muts[0].operator == MutationOperator.POISONED_DOCUMENT


def test_flow_forbidden_without_human_approval_no_approval_missing():
    """A FlowForbidden Property WITHOUT human_approval in allowed_exceptions must not automatically receive APPROVAL_MISSING."""
    prop = Property(
        id=new_id("VPROP"),
        stable_key="test:rule:flow_no_approval",
        name="untrusted-content-cannot-execute-shell",
        description="Shell execution flow test",
        status=PropertyStatus.APPROVED,
        source=PropertySource.RULE_DERIVED,
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="src/in.py::read",
            forbidden_sink_key="src/proc.py::shell",
            allowed_exceptions=["explicit_user_authorization"],
        ),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    gen = WorldGenerator(seed=42)
    worlds = gen.generate_worlds([prop], max_worlds_per_property=3)

    assert len(worlds) == 3
    # Baseline world
    assert worlds[0].authorization.approval_granted is True
    # In the absence of human_approval exception, no APPROVAL_MISSING mutation is injected
    for w in worlds:
        assert not any(m.operator == MutationOperator.APPROVAL_MISSING for m in w.mutations)


def test_flow_forbidden_human_approval_max_worlds_1():
    """If max_worlds=1, only the baseline World is generated, preserving approval_granted=True."""
    prop = Property(
        id=new_id("VPROP"),
        stable_key="test:rule:flow_single",
        name="untrusted-input-single",
        description="Single world test",
        status=PropertyStatus.APPROVED,
        source=PropertySource.RULE_DERIVED,
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="src/in.py::read",
            forbidden_sink_key="src/db.py::write",
            allowed_exceptions=["human_approval"],
        ),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    gen = WorldGenerator(seed=42)
    worlds = gen.generate_worlds([prop], max_worlds_per_property=1)

    assert len(worlds) == 1
    assert worlds[0].authorization.approval_granted is True


def test_flow_forbidden_human_approval_determinism():
    """Generation of approval_missing worlds is completely deterministic for the same seed."""
    prop = Property(
        id=new_id("VPROP"),
        stable_key="test:rule:flow_det",
        name="determinism-test",
        description="Determinism test",
        status=PropertyStatus.APPROVED,
        source=PropertySource.RULE_DERIVED,
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="src/in.py::read",
            forbidden_sink_key="src/db.py::write",
            allowed_exceptions=["human_approval"],
        ),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    gen1 = WorldGenerator(seed=777)
    worlds1 = gen1.generate_worlds([prop], max_worlds_per_property=3)

    gen2 = WorldGenerator(seed=777)
    worlds2 = gen2.generate_worlds([prop], max_worlds_per_property=3)

    assert len(worlds1) == len(worlds2) == 3
    for w1, w2 in zip(worlds1, worlds2, strict=True):
        assert w1.seed == w2.seed
        assert w1.authorization.approval_granted == w2.authorization.approval_granted
        assert [m.operator for m in w1.mutations] == [m.operator for m in w2.mutations]
