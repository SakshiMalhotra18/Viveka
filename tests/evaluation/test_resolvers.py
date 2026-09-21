"""Tests for allowed_exception resolvers."""

from viveka.core.ids import new_id
from viveka.evaluation.models import (
    EvaluationContext,
    ExecutionTrace,
    RuntimeCapabilityBinding,
)
from viveka.evaluation.resolvers import resolve_allowed_exception
from viveka.properties.models import FlowForbiddenOracle, Property
from viveka.properties.vocabulary import PropertyStatus
from viveka.worlds.models import World, WorldAuthorization, WorldUser


def test_resolve_allowed_exception_explicit_user_authorization():
    prop = Property(
        id=new_id("VPROP"),
        stable_key="k1",
        name="p1",
        description="d1",
        status=PropertyStatus.APPROVED,
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="s",
            forbidden_sink_key="k",
        ),
    )
    world = World(
        id=new_id("VWORLD"),
        property_id=prop.id,
        property_stable_key="k1",
        seed=1,
        user=WorldUser(id="admin-1", role="admin"),
        authorization=WorldAuthorization(approval_granted=True),
    )
    trace = ExecutionTrace(trace_id=new_id("VTRC"), execution_id="r1", world_id=world.id)
    ctx = EvaluationContext(
        trace=trace, property=prop, world=world, binding=RuntimeCapabilityBinding()
    )

    res = resolve_allowed_exception("explicit_user_authorization", ctx)
    assert res is True


def test_resolve_allowed_exception_unsupported_returns_none():
    prop = Property(
        id=new_id("VPROP"),
        stable_key="k1",
        name="p1",
        description="d1",
        status=PropertyStatus.APPROVED,
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="s",
            forbidden_sink_key="k",
        ),
    )
    world = World(
        id=new_id("VWORLD"),
        property_id=prop.id,
        property_stable_key="k1",
        seed=1,
    )
    trace = ExecutionTrace(trace_id=new_id("VTRC"), execution_id="r1", world_id=world.id)
    ctx = EvaluationContext(
        trace=trace, property=prop, world=world, binding=RuntimeCapabilityBinding()
    )

    res = resolve_allowed_exception("custom_unsupported_exception_type", ctx)
    assert res is None  # unsupported returns None -> INCONCLUSIVE
