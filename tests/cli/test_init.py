"""Tests for ``viveka init``."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from viveka.cli.app import app
from viveka.core.paths import (
    project_config_path,
    project_gitignore_path,
    project_properties_dir,
)

runner = CliRunner()


def test_init_exits_zero(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0, result.output


def test_init_creates_config_yaml(tmp_path: Path) -> None:
    runner.invoke(app, ["init", str(tmp_path)])
    assert project_config_path(tmp_path).is_file()


def test_init_creates_properties_dir(tmp_path: Path) -> None:
    runner.invoke(app, ["init", str(tmp_path)])
    assert project_properties_dir(tmp_path).is_dir()


def test_init_creates_dot_gitignore(tmp_path: Path) -> None:
    runner.invoke(app, ["init", str(tmp_path)])
    assert project_gitignore_path(tmp_path).is_file()


def test_init_does_not_create_db_in_project(tmp_path: Path) -> None:
    """viveka init must NOT create a SQLite .db file inside the project directory."""
    runner.invoke(app, ["init", str(tmp_path)])
    db_files = list(tmp_path.rglob("*.db"))
    assert db_files == [], f"Found unexpected .db files in project: {db_files}"


def test_init_is_idempotent(tmp_path: Path) -> None:
    """Running viveka init twice must not error or overwrite config."""
    runner.invoke(app, ["init", str(tmp_path)])
    # Corrupt the config to verify it is NOT overwritten
    cfg_path = project_config_path(tmp_path)
    cfg_path.write_text("# sentinel\n", encoding="utf-8")

    result = runner.invoke(app, ["init", str(tmp_path)])
    assert result.exit_code == 0, result.output
    # Sentinel must still be there
    assert "sentinel" in cfg_path.read_text()


def test_init_idempotent_shows_warning(tmp_path: Path) -> None:
    runner.invoke(app, ["init", str(tmp_path)])
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert "already initialised" in result.output.lower() or "!" in result.output


def test_init_missing_directory_exits_error() -> None:
    result = runner.invoke(app, ["init", "/this/path/does/not/exist/at/all"])
    assert result.exit_code != 0


def test_init_output_mentions_config(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert "config.yaml" in result.output


def test_init_output_mentions_mode(tmp_path: Path) -> None:
    result = runner.invoke(app, ["init", str(tmp_path)])
    assert "deterministic" in result.output
