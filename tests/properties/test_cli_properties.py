"""Tests for viveka properties CLI commands: list, suggest, show, approve, reject."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from viveka.cli.app import app

runner = CliRunner()


def _populate_agent_with_search_and_refund(root: Path) -> None:
    (root / "pyproject.toml").write_text("[project]\nname='fin-agent'\n", encoding="utf-8")
    src = root / "src"
    src.mkdir()
    (src / "agent.py").write_text(
        "from .tools import search_docs, refund_order\n"
        "def main():\n"
        "    docs = search_docs('query')\n"
        "    refund_order(123)\n",
        encoding="utf-8",
    )
    (src / "tools.py").write_text(
        "def tool(f): return f\n"
        "@tool\n"
        "def search_docs(q: str):\n"
        "    '''Search docs.'''\n"
        "    return similarity_search(q)\n"
        "@tool\n"
        "def refund_order(order_id: int):\n"
        "    '''Refund order.'''\n"
        "    return stripe.refund(order_id)\n",
        encoding="utf-8",
    )


class TestPropertiesCLI:
    def test_properties_list_empty(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["properties", "list", str(tmp_path)])
        assert result.exit_code == 0
        assert "No properties found" in result.output

    def test_properties_suggest_and_list(self, tmp_path: Path) -> None:
        _populate_agent_with_search_and_refund(tmp_path)

        # Run suggest
        result = runner.invoke(app, ["properties", "suggest", str(tmp_path)])
        assert result.exit_code == 0
        assert "Proposed Candidate Properties" in result.output

        # Run list
        list_res = runner.invoke(app, ["properties", "list", str(tmp_path)])
        assert list_res.exit_code == 0
        assert "candidate" in list_res.output

    def test_properties_show_and_approve(self, tmp_path: Path) -> None:
        _populate_agent_with_search_and_refund(tmp_path)
        runner.invoke(app, ["properties", "suggest", str(tmp_path)])

        # Read property ID from json list
        list_json = runner.invoke(app, ["properties", "list", str(tmp_path), "--json"])
        data = json.loads(list_json.output)
        prop_id = data["properties"][0]["id"]

        # Show property
        show_res = runner.invoke(app, ["properties", "show", prop_id, "--path", str(tmp_path)])
        assert show_res.exit_code == 0
        assert prop_id in show_res.output
        assert "Revision" in show_res.output

        # Approve property
        appr_res = runner.invoke(app, ["properties", "approve", prop_id, "--path", str(tmp_path)])
        assert appr_res.exit_code == 0
        assert "Approved property" in appr_res.output
        assert "rev 2" in appr_res.output

        # Verify status in list is now approved
        list_approved = runner.invoke(
            app, ["properties", "list", str(tmp_path), "--status", "approved"]
        )
        assert list_approved.exit_code == 0
        assert "approved" in list_approved.output

    def test_properties_reject(self, tmp_path: Path) -> None:
        _populate_agent_with_search_and_refund(tmp_path)
        runner.invoke(app, ["properties", "suggest", str(tmp_path)])

        list_json = runner.invoke(app, ["properties", "list", str(tmp_path), "--json"])
        data = json.loads(list_json.output)
        prop_id = data["properties"][0]["id"]

        # Reject property
        rej_res = runner.invoke(app, ["properties", "reject", prop_id, "--path", str(tmp_path)])
        assert rej_res.exit_code == 0
        assert "Rejected property" in rej_res.output
        assert "rev 2" in rej_res.output

    def test_edit_command_removed_from_v1(self, tmp_path: Path) -> None:
        """viveka properties edit was removed from V1 to protect automatic revision history."""
        result = runner.invoke(app, ["properties", "edit", "some-id", "--path", str(tmp_path)])
        assert result.exit_code != 0

    def test_suggest_zero_candidates_case_a(self, tmp_path: Path) -> None:
        """Case A: No capabilities recognized in target repository."""
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname='empty-agent'\n", encoding="utf-8"
        )
        src = tmp_path / "src"
        src.mkdir()
        (src / "math_utils.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["properties", "suggest", str(tmp_path)])
        assert result.exit_code == 0
        assert "Capabilities analyzed" in result.output
        assert "Total candidates inferred" in result.output
        assert "No candidate Properties were inferred." in result.output
        assert "VIVEKA did not recognize capabilities that match its current V1" in result.output
        assert "This result is not a safety determination." in result.output
        assert "viveka inspect" in result.output

    def test_suggest_zero_candidates_case_b(self, tmp_path: Path) -> None:
        """Case B: Capabilities exist, but no applicable source/sink combination."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname='read-agent'\n", encoding="utf-8")
        src = tmp_path / "src"
        src.mkdir()
        (src / "reader.py").write_text(
            "def get_user_data(db, user_id: int):\n"
            "    return db.query(user_id).filter_by(active=True).all()\n",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["properties", "suggest", str(tmp_path)])
        assert result.exit_code == 0
        assert "Capabilities analyzed" in result.output
        assert "Total candidates inferred" in result.output
        assert "No candidate Properties were inferred." in result.output
        assert "none formed an applicable source/sink" in result.output
        assert "This result is not a safety determination." in result.output

    def test_suggest_zero_candidates_case_c(self, tmp_path: Path) -> None:
        """Case C: Relevant source and sink exist, but no directed interaction."""
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname='split-agent'\n", encoding="utf-8"
        )
        src = tmp_path / "src"
        src.mkdir()
        (src / "searcher.py").write_text(
            "import chromadb\n"
            "def query_docs(query_text: str):\n"
            "    client = chromadb.Client()\n"
            "    collection = client.get_collection('docs')\n"
            "    return collection.query(query_texts=[query_text])\n",
            encoding="utf-8",
        )
        (src / "writer.py").write_text(
            "def persist_data(db, item):\n    db.add(item)\n    db.commit()\n",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["properties", "suggest", str(tmp_path)])
        assert result.exit_code == 0
        assert "Capabilities analyzed" in result.output
        assert "Total candidates inferred" in result.output
        assert "No candidate Properties were inferred." in result.output
        assert (
            "Relevant source and sink capabilities were detected, but VIVEKA found" in result.output
        )
        assert "no supported directed source -> sink interaction" in result.output
        assert "This result is not a safety determination." in result.output

    def test_suggest_zero_result_safety_disclaimer(self, tmp_path: Path) -> None:
        """Zero-result output must never use overclaiming safety language."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test-pkg'\n", encoding="utf-8")
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text("x = 1\n", encoding="utf-8")

        result = runner.invoke(app, ["properties", "suggest", str(tmp_path)])
        assert result.exit_code == 0
        output_lower = result.output.lower()
        # Must not claim safety / proof
        assert "application is safe" not in output_lower
        assert "verified safe" not in output_lower
        assert "no vulnerabilities" not in output_lower
        assert "proved" not in output_lower

    def test_suggest_zero_candidates_json(self, tmp_path: Path) -> None:
        """JSON output contract must be preserved for zero-candidate results."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname='json-agent'\n", encoding="utf-8")
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text("x = 1\n", encoding="utf-8")

        result = runner.invoke(app, ["properties", "suggest", str(tmp_path), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["schema_version"] == 1
        assert data["suggested_total"] == 0
        assert data["new_candidates"] == []
        assert data["existing_preserved"] == []
