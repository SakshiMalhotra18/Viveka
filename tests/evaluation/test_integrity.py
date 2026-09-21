"""Tests for property approval and property-world matching integrity checks."""

import pytest

from viveka.core.ids import new_id
from viveka.evaluation.exceptions import (
    PropertyNotApprovedError,
    PropertyWorldMismatchError,
)
from viveka.evaluation.reproduction import execute_reproduction
from viveka.properties.models import FlowForbiddenOracle, Property
from viveka.properties.vocabulary import PropertyStatus
from viveka.worlds.models import World


def test_reproduction_integrity_rejects_unapproved_property():
    prop = Property(
        id=new_id("VPROP"),
        stable_key="key_1",
        name="test-candidate",
        description="Unapproved property",
        status=PropertyStatus.CANDIDATE,  # Not approved!
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="src/read.py::search",
            forbidden_sink_key="src/pay.py::refund",
        ),
    )
    world = World(
        id=new_id("VWORLD"),
        property_id=prop.id,
        property_stable_key="key_1",
        seed=123,
    )

    with pytest.raises(PropertyNotApprovedError, match="must be 'approved'"):
        execute_reproduction(prop, world)


def test_reproduction_integrity_rejects_mismatched_world_property_key():
    prop = Property(
        id=new_id("VPROP"),
        stable_key="key_property_100",
        name="test-approved",
        description="Approved property",
        status=PropertyStatus.APPROVED,
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="src/read.py::search",
            forbidden_sink_key="src/pay.py::refund",
        ),
    )
    world = World(
        id=new_id("VWORLD"),
        property_id=prop.id,
        property_stable_key="key_DIFFERENT_world_200",  # Mismatched!
        seed=123,
    )

    with pytest.raises(PropertyWorldMismatchError, match="does not match property stable key"):
        execute_reproduction(prop, world)
