"""Tests for the static analysis coordinator."""

from __future__ import annotations

import textwrap
from pathlib import Path

from viveka.inspection.analyzer import analyze_python_repository
from viveka.inspection.scanner import scan_repository


class TestAnalyzer:
    def test_complete_repository_analysis(self, tmp_path: Path) -> None:
        src = tmp_path / "src"
        src.mkdir()

        # Tools module
        (src / "tools.py").write_text(
            textwrap.dedent("""\
                def tool(f): return f

                @tool
                def search_docs(query: str) -> list[str]:
                    '''Search documentation files.'''
                    return []
            """),
            encoding="utf-8",
        )

        # Agent module
        (src / "agent.py").write_text(
            textwrap.dedent("""\
                from langgraph.graph import StateGraph
                from .tools import search_docs

                builder = StateGraph()
            """),
            encoding="utf-8",
        )

        # Server module
        (src / "server.py").write_text(
            textwrap.dedent("""\
                from fastapi import FastAPI
                app = FastAPI()

                @app.post("/chat")
                async def chat():
                    return {"status": "ok"}
            """),
            encoding="utf-8",
        )

        scan_summary = scan_repository(tmp_path)
        analysis = analyze_python_repository(tmp_path, scan_summary)

        assert analysis.files_analyzed == 3
        assert analysis.total_functions >= 2
        assert len(analysis.tool_candidates) == 1
        assert analysis.tool_candidates[0].symbol_name == "search_docs"
        assert len(analysis.entrypoint_candidates) >= 1

        fw_names = [f.framework_name for f in analysis.framework_hints]
        assert "LangGraph" in fw_names
        assert "FastAPI" in fw_names

    def test_malicious_code_never_executes(self, tmp_path: Path) -> None:
        # File containing top-level destructive calls and runtime exceptions
        danger_file = tmp_path / "danger.py"
        danger_file.write_text(
            textwrap.dedent("""\
                import os
                # This must be parsed as AST nodes and NEVER executed!
                os.remove("nonexistent_system_file_12345")
                raise RuntimeError("EXECUTION DETECTED! TEST FAILED!")
            """),
            encoding="utf-8",
        )

        scan_summary = scan_repository(tmp_path)
        # Must analyze cleanly without raising RuntimeError or FileNotFoundError
        analysis = analyze_python_repository(tmp_path, scan_summary)
        assert analysis.files_analyzed == 1
        assert len(analysis.parse_failures) == 0

    def test_broken_syntax_file_does_not_halt_analysis(self, tmp_path: Path) -> None:
        (tmp_path / "good.py").write_text("def ok(): return 1\n", encoding="utf-8")
        (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")

        scan_summary = scan_repository(tmp_path)
        analysis = analyze_python_repository(tmp_path, scan_summary)

        assert analysis.files_analyzed == 2
        assert len(analysis.parse_failures) == 1
        assert analysis.parse_failures[0].file_path == "broken.py"
        assert analysis.parse_failures[0].error_type == "SyntaxError"
        # The good file was still parsed
        assert analysis.total_functions == 1
