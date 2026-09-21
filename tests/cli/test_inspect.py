"""Tests for ``viveka inspect`` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from viveka.capabilities import CapabilityAnalysisResult
from viveka.cli.app import app
from viveka.inspection.models import ScanSummary
from viveka.inspection.python_models import StaticAnalysisResult

runner = CliRunner()


def _populate_sample_repo(root: Path) -> None:
    (root / "pyproject.toml").write_text("[project]\nname='sample'\n", encoding="utf-8")
    (root / "README.md").write_text("# Sample Agent\n", encoding="utf-8")
    src = root / "src"
    src.mkdir()
    (src / "agent.py").write_text(
        "from langgraph.graph import StateGraph\n"
        "from .tools import refund\n"
        "builder = StateGraph()\n",
        encoding="utf-8",
    )
    (src / "tools.py").write_text(
        "def tool(f): return f\n"
        "@tool\n"
        "def refund(order_id: int) -> bool:\n"
        "    '''Execute refund.'''\n"
        "    return True\n",
        encoding="utf-8",
    )
    (root / ".env").write_text("KEY=123\n", encoding="utf-8")
    (root / "model.bin").write_bytes(b"\x00\x01\x02\x03")


class TestInspectCommand:
    def test_inspect_dry_run_exits_zero(self, tmp_path: Path) -> None:
        _populate_sample_repo(tmp_path)
        result = runner.invoke(app, ["inspect", str(tmp_path), "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "Repository" in result.output
        assert "Selected for future inspection" in result.output
        assert "agent.py" in result.output
        assert "No file contents were executed." in result.output

    def test_inspect_full_static_analysis_output(self, tmp_path: Path) -> None:
        _populate_sample_repo(tmp_path)
        result = runner.invoke(app, ["inspect", str(tmp_path)])
        assert result.exit_code == 0, result.output
        assert "Python Static Analysis" in result.output
        assert "Modules analyzed" in result.output
        assert "LangGraph" in result.output
        assert "Tool candidates" in result.output
        assert "refund" in result.output
        assert "Capability Analysis (Static)" in result.output
        assert "Capabilities inferred" in result.output
        assert "No file contents were executed." in result.output

    def test_inspect_json_output_envelope(self, tmp_path: Path) -> None:
        _populate_sample_repo(tmp_path)
        result = runner.invoke(app, ["inspect", str(tmp_path), "--json"])
        assert result.exit_code == 0, result.output

        # Verify stdout is clean valid JSON envelope
        data = json.loads(result.output)
        assert data["schema_version"] == 1
        assert "scan" in data
        assert "static_analysis" in data
        assert "capability_analysis" in data

        scan = ScanSummary.model_validate(data["scan"])
        assert scan.files_selected == 4
        assert scan.sensitive_files_detected == 1
        assert scan.binary_files_skipped == 1

        analysis = StaticAnalysisResult.model_validate(data["static_analysis"])
        assert analysis.files_analyzed == 2
        assert len(analysis.tool_candidates) == 1
        assert analysis.tool_candidates[0].symbol_name == "refund"

        cap_analysis = CapabilityAnalysisResult.model_validate(data["capability_analysis"])
        assert isinstance(cap_analysis.capabilities, list)
        assert isinstance(cap_analysis.trust_boundaries, list)
        assert isinstance(cap_analysis.graph.nodes, list)
        assert isinstance(cap_analysis.graph.edges, list)

    def test_inspect_dry_run_json(self, tmp_path: Path) -> None:
        _populate_sample_repo(tmp_path)
        result = runner.invoke(app, ["inspect", str(tmp_path), "--dry-run", "--json"])
        assert result.exit_code == 0, result.output

        data = json.loads(result.output)
        assert data["schema_version"] == 1
        assert "scan" in data
        assert data["static_analysis"] is None
        assert data["capability_analysis"] is None

    def test_inspect_with_cli_exclude(self, tmp_path: Path) -> None:
        _populate_sample_repo(tmp_path)
        result = runner.invoke(
            app, ["inspect", str(tmp_path), "--json", "--exclude", "src/tools.py"]
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        scan = ScanSummary.model_validate(data["scan"])
        selected_names = [f.relative_path for f in scan.selected_files]
        assert "src/tools.py" not in selected_names
        assert "src/agent.py" in selected_names

    def test_inspect_with_cli_include(self, tmp_path: Path) -> None:
        _populate_sample_repo(tmp_path)
        result = runner.invoke(app, ["inspect", str(tmp_path), "--json", "--include", "src/**"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        scan = ScanSummary.model_validate(data["scan"])
        selected_names = [f.relative_path for f in scan.selected_files]
        assert "src/agent.py" in selected_names
        assert "README.md" not in selected_names

    def test_inspect_nonexistent_dir_fails(self) -> None:
        result = runner.invoke(app, ["inspect", "/path/to/nonexistent/directory/xyz"])
        assert result.exit_code != 0
