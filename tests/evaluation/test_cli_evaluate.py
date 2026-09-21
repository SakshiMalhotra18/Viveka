"""Tests for viveka evaluate CLI command."""

import json

from typer.testing import CliRunner

from viveka.cli.app import app
from viveka.core.ids import new_id
from viveka.properties.models import FlowForbiddenOracle, Property
from viveka.properties.store import PropertyStore
from viveka.properties.vocabulary import PropertySource, PropertyStatus
from viveka.worlds.models import World
from viveka.worlds.store import WorldStore

runner = CliRunner()


def test_cli_evaluate_smoke(tmp_path):
    # Setup approved property and matching world
    prop_store = PropertyStore(tmp_path)
    prop = Property(
        id=new_id("VPROP"),
        stable_key="test_flow_key_cli",
        name="test-cli-flow",
        description="CLI flow test property",
        status=PropertyStatus.APPROVED,  # Approved!
        source=PropertySource.RULE_DERIVED,
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="src/read.py::search",
            forbidden_sink_key="src/pay.py::refund",
        ),
    )
    prop_store.save(prop)

    world_store = WorldStore(tmp_path)
    world = World(
        id=new_id("VWORLD"),
        property_id=prop.id,
        property_stable_key=prop.stable_key,  # Matching!
        seed=123,
    )
    world_store.save(world)

    res = runner.invoke(
        app,
        [
            "evaluate",
            prop.id,
            world.id,
            "--path",
            str(tmp_path),
            "--runs",
            "2",
            "--minimum-violations",
            "1",
        ],
    )
    assert res.exit_code == 0
    assert "Reproduction Testing Results" in res.output
    assert prop.id in res.output


def test_cli_evaluate_json(tmp_path):
    prop_store = PropertyStore(tmp_path)
    prop = Property(
        id=new_id("VPROP"),
        stable_key="test_json_key",
        name="test-json-flow",
        description="JSON flow test",
        status=PropertyStatus.APPROVED,
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="src/search.py::knowledge_search",
            forbidden_sink_key="src/refund.py::refund_create",
        ),
    )
    prop_store.save(prop)

    world_store = WorldStore(tmp_path)
    world = World(
        id=new_id("VWORLD"),
        property_id=prop.id,
        property_stable_key=prop.stable_key,
        seed=42,
    )
    world_store.save(world)

    res = runner.invoke(
        app,
        ["evaluate", prop.id, world.id, "--path", str(tmp_path), "-r", "2", "-m", "1", "--json"],
    )
    assert res.exit_code == 0
    data = json.loads(res.output)
    assert data["property_id"] == prop.id
    assert "total_runs" in data
    assert len(data["runs_detail"]) == 2
