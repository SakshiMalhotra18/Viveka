"""
CLI command integration tests for viveka reduce.
"""

from __future__ import annotations

from typer.testing import CliRunner

from viveka.cli.app import app
from viveka.properties.models import FlowForbiddenOracle, Property
from viveka.properties.store import PropertyStore
from viveka.properties.vocabulary import PropertyStatus
from viveka.worlds.models import World, WorldDocument
from viveka.worlds.store import WorldStore

runner = CliRunner()


def test_cli_reduce_json_output(tmp_path) -> None:
    prop_store = PropertyStore(tmp_path)
    prop = Property(
        id="VPROP-01JY8M7KFQZRVF2BNXD3TYA9WG",
        name="Flow Forbidden Demo",
        description="Forbidden flow test",
        oracle=FlowForbiddenOracle(
            untrusted_source_key="src.search::knowledge_search",
            forbidden_sink_key="src.payment::refund_order",
        ),
        status=PropertyStatus.APPROVED,
        stable_key="prop.flow_demo",
    )
    prop_store.save(prop)

    world_store = WorldStore(tmp_path)
    world = World(
        id="VWORLD-01JY8M7KFQZRVF2BNXD3TYA9WG",
        property_id=prop.id,
        property_stable_key=prop.stable_key,
        seed=12345,
    )
    world.retrieval.documents.append(WorldDocument(id="doc-1", content="untrusted context"))
    world_store.save(world)

    result = runner.invoke(
        app,
        [
            "reduce",
            prop.id,
            world.id,
            "--path",
            str(tmp_path),
            "--runs",
            "1",
            "--minimum-violations",
            "1",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert "reduction_id" in result.stdout
