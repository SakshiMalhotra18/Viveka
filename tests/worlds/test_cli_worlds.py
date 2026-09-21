"""Tests for Phase 6 CLI subcommands: viveka worlds generate, list, show."""

import json

from typer.testing import CliRunner

from viveka.cli.app import app
from viveka.core.ids import new_id
from viveka.properties.models import FlowForbiddenOracle, Property
from viveka.properties.store import PropertyStore
from viveka.properties.vocabulary import PropertySource, PropertyStatus
from viveka.worlds.store import WorldStore

runner = CliRunner()


def test_cli_worlds_generate_no_approved_properties(tmp_path):
    # Initialize config
    config_dir = tmp_path / ".viveka"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text("version: 1\nproject:\n  name: test\n")

    res = runner.invoke(app, ["worlds", "generate", str(tmp_path)])
    assert res.exit_code == 0
    assert "No approved properties found" in res.output


def test_cli_worlds_generate_and_list_and_show(tmp_path):
    # Setup project with config and an approved property
    config_dir = tmp_path / ".viveka"
    config_dir.mkdir()
    (config_dir / "config.yaml").write_text("version: 1\nproject:\n  name: test\n")

    prop_store = PropertyStore(tmp_path)
    prop = Property(
        id=new_id("VPROP"),
        stable_key="test_flow_key",
        name="test-flow-prop",
        description="Test flow description",
        status=PropertyStatus.APPROVED,
        source=PropertySource.RULE_DERIVED,
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="src/read.py::search",
            forbidden_sink_key="src/pay.py::refund",
        ),
    )
    prop_store.save(prop)

    # 1. Generate worlds
    gen_res = runner.invoke(app, ["worlds", "generate", str(tmp_path), "--seed", "123", "-m", "2"])
    assert gen_res.exit_code == 0
    assert "Generated 2 world(s)" in gen_res.output

    # Check store directly
    world_store = WorldStore(tmp_path)
    worlds = world_store.load_all()
    assert len(worlds) == 2
    w_id = worlds[0].id

    # 2. List worlds
    list_res = runner.invoke(app, ["worlds", "list", str(tmp_path)])
    assert list_res.exit_code == 0
    assert w_id in list_res.output

    # 3. List worlds with --json
    json_list_res = runner.invoke(app, ["worlds", "list", str(tmp_path), "--json"])
    assert json_list_res.exit_code == 0
    parsed = json.loads(json_list_res.output)
    assert parsed["total_worlds"] == 2

    # 4. Show world
    show_res = runner.invoke(app, ["worlds", "show", w_id, "--path", str(tmp_path)])
    assert show_res.exit_code == 0
    assert w_id in show_res.output
