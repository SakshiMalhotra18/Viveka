"""
Heuristic framework detection for VIVEKA repository inspection.

Analyzes imports, decorators, and function calls to infer likely AI and web
frameworks present in the project with concrete file:line evidence.
"""

from __future__ import annotations

from viveka.inspection.python_models import Confidence, FrameworkHint, PythonModule


def detect_framework_hints(modules: list[PythonModule]) -> list[FrameworkHint]:
    """Analyze parsed modules and infer likely framework presence."""
    hints: list[FrameworkHint] = []

    # Accumulators for evidence items
    langgraph_evidence: list[str] = []
    langchain_evidence: list[str] = []
    openai_evidence: list[str] = []
    mcp_evidence: list[str] = []
    fastapi_evidence: list[str] = []
    flask_evidence: list[str] = []
    pydanticai_evidence: list[str] = []

    for mod in modules:
        if mod.parse_status != "ok":
            continue

        # 1. Imports Analysis
        for imp in mod.imports:
            base_mod = imp.module.split(".")[0]
            full_imp = f"{imp.module}.{imp.imported_name}" if imp.imported_name else imp.module

            # LangGraph
            if base_mod == "langgraph" or imp.imported_name == "StateGraph":
                langgraph_evidence.append(f"{mod.path}:{imp.line} import {full_imp}")

            # LangChain
            if base_mod in ("langchain", "langchain_core", "langchain_community"):
                langchain_evidence.append(f"{mod.path}:{imp.line} import {full_imp}")

            # OpenAI Agents / Swarm
            if base_mod in ("agents", "swarm") or imp.module.startswith("openai.agents"):
                openai_evidence.append(f"{mod.path}:{imp.line} import {full_imp}")

            # MCP
            if base_mod == "mcp" or imp.imported_name in ("FastMCP", "Server"):
                mcp_evidence.append(f"{mod.path}:{imp.line} import {full_imp}")

            # FastAPI
            if base_mod == "fastapi":
                fastapi_evidence.append(f"{mod.path}:{imp.line} import {full_imp}")

            # Flask
            if base_mod == "flask":
                flask_evidence.append(f"{mod.path}:{imp.line} import {full_imp}")

            # Pydantic AI
            if base_mod == "pydantic_ai":
                pydanticai_evidence.append(f"{mod.path}:{imp.line} import {full_imp}")

        # 2. Decorators & Calls Analysis
        all_functions = list(mod.functions)
        for cls in mod.classes:
            all_functions.extend(cls.methods)

        for fn in all_functions:
            for dec in fn.decorators:
                d_name = dec.name.lower()
                if "mcp.tool" in d_name:
                    mcp_evidence.append(f"{mod.path}:{dec.line} decorator @{dec.name}")
                elif d_name in ("tool", "langchain_core.tools.tool"):
                    langchain_evidence.append(f"{mod.path}:{dec.line} decorator @{dec.name}")
                elif d_name in ("function_tool", "openai.agents.function_tool"):
                    openai_evidence.append(f"{mod.path}:{dec.line} decorator @{dec.name}")
                elif any(
                    d_name.startswith(p)
                    for p in ("app.post", "app.get", "router.post", "router.get", "app.put")
                ):
                    fastapi_evidence.append(f"{mod.path}:{dec.line} route decorator @{dec.name}")
                elif d_name.startswith("app.route"):
                    flask_evidence.append(f"{mod.path}:{dec.line} route decorator @{dec.name}")
                elif "agent.tool" in d_name:
                    pydanticai_evidence.append(f"{mod.path}:{dec.line} decorator @{dec.name}")

            # Function calls inside
            for call in fn.calls:
                c_name = call.callee
                if c_name in ("StateGraph", "graph.compile", "graph.invoke"):
                    langgraph_evidence.append(f"{mod.path}:{call.line} call {c_name}(...)")
                elif c_name.startswith("FastMCP"):
                    mcp_evidence.append(f"{mod.path}:{call.line} call {c_name}(...)")

        # Top-level calls
        for call in mod.calls:
            c_name = call.callee
            if c_name in ("StateGraph", "graph.compile"):
                langgraph_evidence.append(f"{mod.path}:{call.line} call {c_name}(...)")
            elif c_name.startswith("FastMCP"):
                mcp_evidence.append(f"{mod.path}:{call.line} call {c_name}(...)")

    # Build FrameworkHint objects
    def _add_hint(name: str, ev_list: list[str]) -> None:
        if not ev_list:
            return
        conf = Confidence.HIGH if len(ev_list) >= 2 else Confidence.MEDIUM
        hints.append(
            FrameworkHint(
                framework_name=name,
                confidence=conf,
                evidence=ev_list[:10],  # Bounded evidence
            )
        )

    _add_hint("LangGraph", langgraph_evidence)
    _add_hint("LangChain", langchain_evidence)
    _add_hint("OpenAI Agents SDK", openai_evidence)
    _add_hint("MCP Python SDK", mcp_evidence)
    _add_hint("FastAPI", fastapi_evidence)
    _add_hint("Flask", flask_evidence)
    _add_hint("Pydantic AI", pydanticai_evidence)

    hints.sort(key=lambda h: h.framework_name)
    return hints
