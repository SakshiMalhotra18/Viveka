"""Tests for tool and entrypoint candidate detection and import graphs."""

from __future__ import annotations

import textwrap
from pathlib import Path

from viveka.inspection.python_ast import parse_python_module
from viveka.inspection.python_models import Confidence
from viveka.inspection.symbols import (
    build_import_graph,
    detect_entrypoint_candidates,
    detect_tool_candidates,
)


class TestToolCandidates:
    def test_decorated_tool_candidate(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            def tool(func): return func

            @tool
            def send_email(to: str, subject: str) -> bool:
                '''Send an email message.'''
                return True
        """)
        p = tmp_path / "email.py"
        p.write_text(code, encoding="utf-8")
        mod = parse_python_module(p, "src/email.py")

        tools = detect_tool_candidates([mod])
        assert len(tools) == 1
        assert tools[0].symbol_name == "send_email"
        assert tools[0].confidence == Confidence.HIGH
        assert tools[0].file_path == "src/email.py"

    def test_tool_file_function_candidate(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            def calculate_discount(price: float) -> float:
                '''Calculate customer discount.'''
                return price * 0.9
        """)
        p = tmp_path / "pricing_tools.py"
        p.write_text(code, encoding="utf-8")
        mod = parse_python_module(p, "src/pricing_tools.py")

        tools = detect_tool_candidates([mod])
        assert len(tools) == 1
        assert tools[0].symbol_name == "calculate_discount"
        assert tools[0].confidence == Confidence.MEDIUM


class TestEntrypointCandidates:
    def test_fastapi_route_entrypoint(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            from fastapi import FastAPI
            app = FastAPI()

            @app.post("/api/v1/chat")
            async def handle_chat(prompt: str):
                return {"reply": prompt}
        """)
        p = tmp_path / "main.py"
        p.write_text(code, encoding="utf-8")
        mod = parse_python_module(p, "main.py")

        entrypoints = detect_entrypoint_candidates([mod])
        assert len(entrypoints) == 1
        assert entrypoints[0].entrypoint_type == "fastapi_route"
        assert entrypoints[0].route_method == "POST"
        assert entrypoints[0].route_path == "/api/v1/chat"
        assert entrypoints[0].confidence == Confidence.HIGH

    def test_stategraph_workflow_entrypoint(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            from langgraph.graph import StateGraph
            graph = StateGraph()
        """)
        p = tmp_path / "workflow.py"
        p.write_text(code, encoding="utf-8")
        mod = parse_python_module(p, "workflow.py")

        entrypoints = detect_entrypoint_candidates([mod])
        assert any(ep.entrypoint_type == "stategraph" for ep in entrypoints)


class TestImportGraph:
    def test_local_and_external_imports(self, tmp_path: Path) -> None:
        # Module 1: src/tools.py
        tools_code = "def fetch_data(): pass\n"
        (tmp_path / "tools.py").write_text(tools_code, encoding="utf-8")
        mod_tools = parse_python_module(tmp_path / "tools.py", "src/tools.py")

        # Module 2: src/agent.py (imports local tools and external requests)
        agent_code = textwrap.dedent("""\
            import requests
            import json
            from .tools import fetch_data
        """)
        (tmp_path / "agent.py").write_text(agent_code, encoding="utf-8")
        mod_agent = parse_python_module(tmp_path / "agent.py", "src/agent.py")

        local_edges, externals = build_import_graph([mod_tools, mod_agent])

        # Local edge from agent.py to tools.py
        assert len(local_edges) == 1
        assert local_edges[0].source_file == "src/agent.py"
        assert local_edges[0].target_file == "src/tools.py"
        assert local_edges[0].imported_symbol == "fetch_data"

        # External imports (requests included, stdlib json excluded)
        assert "requests" in externals
        assert "json" not in externals
