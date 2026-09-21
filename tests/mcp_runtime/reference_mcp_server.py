"""
Reference stdio MCP server for VIVEKA Phase 14 runtime adapter tests.
Uses official MCP Python SDK v2 MCPServer.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from mcp import UrlElicitationRequiredError
from mcp.server.mcpserver import MCPServer
from mcp.types import CallToolResult, ElicitRequestURLParams, TextContent

mcp = MCPServer("viveka-reference-mcp-server")


@mcp.tool(name="agent.run")
async def run_agent(
    execution_id: str = "",
    world_id: str = "",
    seed: int = 0,
    context: dict[str, Any] | None = None,
) -> Any:
    """Default agent.run tool."""
    # Write invocation count marker file if INVOCATION_LOG_FILE env is provided
    counter_file = os.environ.get("VIVEKA_TEST_INVOCATION_COUNTER_FILE")
    if counter_file:
        p = Path(counter_file)
        val = 0
        if p.exists():
            try:
                val = int(p.read_text(encoding="utf-8").strip())
            except Exception:
                val = 0
        p.write_text(str(val + 1), encoding="utf-8")

    ctx = context or {}
    mode = "success"
    if isinstance(ctx, dict):
        msg = ctx.get("message", "")
        if msg and msg != "Hello agent":
            mode = msg
        state = ctx.get("state", {})
        if isinstance(state, dict):
            mem = state.get("memory", {})
            if isinstance(mem, dict) and "test_mode" in mem:
                mode = mem["test_mode"]

    if mode == "elicitation":
        raise UrlElicitationRequiredError(
            elicitations=[
                ElicitRequestURLParams(
                    url="https://example.com/login",
                    id="auth-1",
                    message="Interactive login required",
                )
            ],
            message="Interactive elicitation requested by server",
        )
    elif mode == "secret_check":
        secret = os.environ.get("TARGET_API_KEY", "MISSING_SECRET")
        return json.dumps({"output": f"Received secret: {secret}"})
    elif mode == "target_error":
        return CallToolResult(
            isError=True,
            content=[TextContent(type="text", text="Target tool encountered internal error")],
        )
    elif mode == "non_instrumented":
        return json.dumps({"output": f"Processed world {world_id} successfully"})
    elif mode == "instrumented":
        return json.dumps(
            {
                "output": f"Processed world {world_id} with telemetry",
                "viveka_telemetry": {
                    "schema_version": 1,
                    "complete": True,
                    "events": [
                        {
                            "event_id": "REVT-01",
                            "sequence": 1,
                            "event_type": "tool_call",
                            "tool_name": "read_file",
                            "tool_args": {"path": "/etc/hosts"},
                        },
                        {
                            "event_id": "REVT-02",
                            "sequence": 2,
                            "event_type": "tool_result",
                            "tool_name": "read_file",
                            "tool_result": "127.0.0.1 localhost",
                        },
                    ],
                },
            }
        )
    elif mode == "missing_output":
        return json.dumps({"status": "ok"})
    elif mode == "bad_telemetry":
        return json.dumps(
            {
                "output": "ok",
                "viveka_telemetry": {"schema_version": 99, "complete": True},
            }
        )
    elif mode == "timeout":
        await asyncio.sleep(10.0)
        return json.dumps({"output": "slept"})
    elif mode == "invalid_json":
        return "This is not JSON data at all"
    else:
        return json.dumps({"output": f"Default output for {world_id}"})


@mcp.tool(name="custom.tool")
async def custom_tool(
    execution_id: str = "",
    world_id: str = "",
    seed: int = 0,
    context: dict[str, Any] | None = None,
) -> str:
    """Custom tool name test."""
    return json.dumps({"output": "custom tool output"})


if __name__ == "__main__":
    asyncio.run(mcp.run_stdio_async())
