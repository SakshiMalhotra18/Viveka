"""Tests for ``viveka doctor``."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from viveka.cli.app import app
from viveka.core.paths import project_config_path

runner = CliRunner()


def _init(tmp_path: Path) -> None:
    """Helper: run viveka init in tmp_path."""
    runner.invoke(app, ["init", str(tmp_path)])


class TestDoctorReady:
    def test_exits_zero_with_init(self, tmp_path: Path) -> None:
        _init(tmp_path)
        result = runner.invoke(app, ["doctor", str(tmp_path)])
        # May exit 1 only if Ollama is required; default mode is deterministic
        # For the deterministic mode, missing Ollama is NOT critical.
        # So exit code must be 0 in a clean environment.
        assert result.exit_code == 0, result.output

    def test_output_contains_ready(self, tmp_path: Path) -> None:
        _init(tmp_path)
        result = runner.invoke(app, ["doctor", str(tmp_path)])
        assert "Ready" in result.output

    def test_output_contains_python_version(self, tmp_path: Path) -> None:
        _init(tmp_path)
        result = runner.invoke(app, ["doctor", str(tmp_path)])
        py = f"{sys.version_info.major}.{sys.version_info.minor}"
        assert py in result.output

    def test_output_mentions_deterministic_mode(self, tmp_path: Path) -> None:
        _init(tmp_path)
        result = runner.invoke(app, ["doctor", str(tmp_path)])
        assert "deterministic" in result.output.lower()


class TestDoctorMissingConfig:
    def test_exits_nonzero_without_init(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["doctor", str(tmp_path)])
        assert result.exit_code != 0

    def test_output_suggests_init(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["doctor", str(tmp_path)])
        assert "viveka init" in result.output or "init" in result.output.lower()


class TestDoctorOllamaWarning:
    def test_missing_ollama_in_deterministic_mode_is_not_critical(self, tmp_path: Path) -> None:
        """Ollama not present must NOT cause exit code 1 when mode=deterministic."""
        _init(tmp_path)
        with patch(
            "viveka.cli.commands.doctor._check_ollama",
            return_value=(False, "Ollama not detected"),
        ):
            result = runner.invoke(app, ["doctor", str(tmp_path)])
        assert result.exit_code == 0, result.output

    def test_missing_ollama_in_local_mode_is_critical(self, tmp_path: Path) -> None:
        """Ollama not present MUST cause exit code 1 when mode=local."""
        import textwrap

        _init(tmp_path)
        cfg_path = project_config_path(tmp_path)
        cfg_path.write_text(
            textwrap.dedent("""\
                version: 1
                reasoning:
                  mode: local
                  provider:
                    type: ollama
            """),
            encoding="utf-8",
        )
        with patch(
            "viveka.cli.commands.doctor._check_ollama",
            return_value=(False, "Ollama not detected"),
        ):
            result = runner.invoke(app, ["doctor", str(tmp_path)])
        assert result.exit_code == 1, result.output


class TestDoctorPythonVersionCheck:
    def test_old_python_is_critical(self, tmp_path: Path) -> None:
        _init(tmp_path)
        # Patch _check_python directly to simulate an old Python report
        with patch(
            "viveka.cli.commands.doctor._check_python",
            return_value=(False, "3.10.0"),
        ):
            result = runner.invoke(app, ["doctor", str(tmp_path)])
        assert result.exit_code == 1, result.output
