"""Tests for heuristic framework detection."""

from __future__ import annotations

import textwrap
from pathlib import Path

from viveka.inspection.frameworks import detect_framework_hints
from viveka.inspection.python_ast import parse_python_module


class TestFrameworkDetection:
    def test_langgraph_detection(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            from langgraph.graph import StateGraph
            builder = StateGraph()
            graph = builder.compile()
        """)
        p = tmp_path / "graph.py"
        p.write_text(code, encoding="utf-8")
        mod = parse_python_module(p, "graph.py")

        hints = detect_framework_hints([mod])
        names = [h.framework_name for h in hints]
        assert "LangGraph" in names

    def test_fastapi_detection(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            from fastapi import FastAPI
            app = FastAPI()

            @app.post("/chat")
            async def chat():
                return {"status": "ok"}
        """)
        p = tmp_path / "server.py"
        p.write_text(code, encoding="utf-8")
        mod = parse_python_module(p, "server.py")

        hints = detect_framework_hints([mod])
        names = [h.framework_name for h in hints]
        assert "FastAPI" in names

    def test_mcp_detection(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            from mcp.server.fastmcp import FastMCP
            mcp = FastMCP("demo")

            @mcp.tool()
            def query_db(sql: str) -> str:
                return "result"
        """)
        p = tmp_path / "mcp_app.py"
        p.write_text(code, encoding="utf-8")
        mod = parse_python_module(p, "mcp_app.py")

        hints = detect_framework_hints([mod])
        names = [h.framework_name for h in hints]
        assert "MCP Python SDK" in names

    def test_openai_agents_sdk_detection(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            from agents import Agent, function_tool

            @function_tool
            def get_weather(city: str) -> str:
                return "sunny"
        """)
        p = tmp_path / "openai_agent.py"
        p.write_text(code, encoding="utf-8")
        mod = parse_python_module(p, "openai_agent.py")

        hints = detect_framework_hints([mod])
        names = [h.framework_name for h in hints]
        assert "OpenAI Agents SDK" in names

    def test_langchain_detection(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            from langchain_core.tools import tool

            @tool
            def search(query: str) -> str:
                return "results"
        """)
        p = tmp_path / "lc_tools.py"
        p.write_text(code, encoding="utf-8")
        mod = parse_python_module(p, "lc_tools.py")

        hints = detect_framework_hints([mod])
        names = [h.framework_name for h in hints]
        assert "LangChain" in names

    def test_unknown_framework_no_hints(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
            import math
            def compute(x: float) -> float:
                return math.sqrt(x)
        """)
        p = tmp_path / "plain.py"
        p.write_text(code, encoding="utf-8")
        mod = parse_python_module(p, "plain.py")

        hints = detect_framework_hints([mod])
        assert hints == []
