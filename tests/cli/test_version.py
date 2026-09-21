"""Tests for ``viveka version``."""

from __future__ import annotations

from typer.testing import CliRunner

from viveka import __version__
from viveka.cli.app import app

runner = CliRunner()


def test_version_exits_zero() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0, result.output


def test_version_shows_version_string() -> None:
    result = runner.invoke(app, ["version"])
    assert __version__ in result.output


def test_version_shows_python_string() -> None:
    result = runner.invoke(app, ["version"])
    assert "Python" in result.output


def test_help_exits_zero() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output


def test_help_mentions_init() -> None:
    result = runner.invoke(app, ["--help"])
    assert "init" in result.output
