"""
CLI tests for `viveka suggest` command group.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from viveka.cli.app import app

runner = CliRunner()


def test_suggest_properties_disabled_reasoning_fails_cleanly(tmp_path: Path) -> None:
    # Init project with default config (reasoning.mode = deterministic)
    res_init = runner.invoke(app, ["init", str(tmp_path)])
    assert res_init.exit_code == 0

    res = runner.invoke(app, ["suggest", "properties", str(tmp_path)])
    assert res.exit_code != 0
    assert "Reasoning is disabled" in res.output or "Configuration Error" in res.output


def test_suggest_worlds_missing_property_fails(tmp_path: Path) -> None:
    res_init = runner.invoke(app, ["init", str(tmp_path)])
    assert res_init.exit_code == 0

    res = runner.invoke(app, ["suggest", "worlds", str(tmp_path), "--property", "non-existent"])
    assert res.exit_code != 0
