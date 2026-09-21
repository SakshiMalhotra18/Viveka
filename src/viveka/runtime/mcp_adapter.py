"""
VIVEKA Phase 14: Model Context Protocol (MCP) Runtime Adapter.

Provides McpRuntimeAdapter for executing target agents exposed through MCP stdio transport.
Uses the official Model Context Protocol Python SDK v2 high-level Client.
Enforces per-execution fresh client session, contained thread event-loop bridge,
tool-discovery pagination contract, secret isolation contract, bounded execution timeout,
versioned telemetry contract, and evidence-preserving provenance.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from viveka.core.ids import new_id
from viveka.runtime.adapter import BaseRuntimeAdapter
from viveka.runtime.models import RawEvent, RuntimeRequest, RuntimeResult, TargetSpec
from viveka.runtime.python_adapter import AdapterError
from viveka.runtime.vocabulary import EventOrigin, ExecutionStatus, RawEventType

try:
    import mcp
    from mcp import (
        Client,
        InputRequiredRoundsExceededError,
        StdioServerParameters,
        UrlElicitationRequiredError,
    )
    from mcp.types import CallToolResult

    HAS_MCP = True
except ImportError:
    HAS_MCP = False
    mcp = None  # type: ignore[assignment]
    Client = None  # type: ignore[assignment, misc]
    StdioServerParameters = None  # type: ignore[assignment, misc]
    CallToolResult = None  # type: ignore[assignment, misc]
    InputRequiredRoundsExceededError = Exception  # type: ignore[assignment, misc]
    UrlElicitationRequiredError = Exception  # type: ignore[assignment, misc]

T = TypeVar("T")


class McpRuntimeAdapter(BaseRuntimeAdapter):
    """Runtime adapter for invoking target agents exposed through MCP stdio transport."""

    def __init__(self) -> None:
        self.command: str = ""
        self.args: list[str] = []
        self.tool: str = "agent.run"
        self.timeout_seconds: float = 30.0
        self.env_from_host: dict[str, str] = {}
        self._target_spec: TargetSpec | None = None

    def load_target(self, spec: TargetSpec) -> None:
        """Load and validate the MCP target specification."""
        if not HAS_MCP:
            raise AdapterError(
                "MCP support requires the optional 'mcp' extra. "
                "Install via `pip install viveka-engine[mcp]`."
            )

        self._target_spec = spec
        opts = spec.options or {}

        transport = str(opts.get("transport", "stdio")).lower()
        if transport != "stdio":
            raise AdapterError(
                f"Unsupported transport '{transport}' for MCP target. "
                "Only 'stdio' transport is supported in V1."
            )

        command = (opts.get("command") or spec.import_path or spec.endpoint or "").strip()
        if not command:
            raise AdapterError(
                "MCP target spec requires a valid command in spec.options['command'] or spec.import_path."
            )

        self.command = command

        # Parse args from list or JSON string
        raw_args = opts.get("args", [])
        if isinstance(raw_args, str):
            try:
                parsed_args = json.loads(raw_args)
                if isinstance(parsed_args, list):
                    self.args = [str(a) for a in parsed_args]
                else:
                    self.args = [raw_args]
            except Exception:
                self.args = [raw_args] if raw_args else []
        elif isinstance(raw_args, list):
            self.args = [str(a) for a in raw_args]
        else:
            self.args = []

        self.tool = opts.get("tool", "agent.run")

        try:
            self.timeout_seconds = float(opts.get("timeout_seconds", 30.0))
        except ValueError:
            self.timeout_seconds = 30.0

        # Parse env_from_host dict or JSON string mapping: TARGET_ENV_VAR -> HOST_ENV_VAR
        raw_env = opts.get("env_from_host", {})
        if isinstance(raw_env, str):
            try:
                parsed_env = json.loads(raw_env)
                if isinstance(parsed_env, dict):
                    self.env_from_host = {str(k): str(v) for k, v in parsed_env.items()}
                else:
                    self.env_from_host = {}
            except Exception:
                self.env_from_host = {}
        elif isinstance(raw_env, dict):
            self.env_from_host = {str(k): str(v) for k, v in raw_env.items()}
        else:
            self.env_from_host = {}

    def execute(self, request: RuntimeRequest) -> RuntimeResult:
        """Execute a single trial run against the MCP target agent."""
        if not HAS_MCP:
            raise AdapterError(
                "MCP support requires the optional 'mcp' extra. "
                "Install via `pip install viveka-engine[mcp]`."
            )
        if not self.command:
            raise AdapterError("McpRuntimeAdapter.load_target() must be called before execute().")

        timeout = request.timeout_seconds if request.timeout_seconds > 0 else self.timeout_seconds
        start_time = time.perf_counter()

        payload = {
            "execution_id": request.execution_id,
            "world_id": request.world_id,
            "seed": request.seed,
            "context": request.context.model_dump(mode="json"),
        }

        # Resolve env_from_host secrets at execution time
        env = {str(k): str(v) for k, v in os.environ.items() if not k.startswith("=")}
        for target_key, host_env_var in self.env_from_host.items():
            secret_val = os.environ.get(host_env_var)
            if secret_val is None:
                execution_ms = (time.perf_counter() - start_time) * 1000.0
                return RuntimeResult(
                    execution_id=request.execution_id,
                    world_id=request.world_id,
                    status=ExecutionStatus.ADAPTER_ERROR,
                    error_message=(
                        f"Missing required host environment variable '{host_env_var}' "
                        f"configured for MCP secret '{target_key}'."
                    ),
                    execution_time_ms=execution_ms,
                )
            env[target_key] = secret_val

        # Execute inside a contained dedicated thread with its own private event loop.
        # This guarantees synchronous execution without relying on naive asyncio.run(),
        # allowing execution from both ordinary sync callers and active-event-loop contexts.
        try:
            return self._run_async_in_contained_thread(
                lambda: self._execute_async(request, payload, timeout, start_time, env),
                timeout=timeout,
            )
        except AdapterError as exc:
            execution_ms = (time.perf_counter() - start_time) * 1000.0
            return RuntimeResult(
                execution_id=request.execution_id,
                world_id=request.world_id,
                status=ExecutionStatus.ADAPTER_ERROR,
                error_message=str(exc),
                execution_time_ms=execution_ms,
            )
        except Exception as exc:
            execution_ms = (time.perf_counter() - start_time) * 1000.0
            return RuntimeResult(
                execution_id=request.execution_id,
                world_id=request.world_id,
                status=ExecutionStatus.ADAPTER_ERROR,
                error_message=f"Unexpected error executing MCP target: {exc}",
                execution_time_ms=execution_ms,
            )

    def _run_async_in_contained_thread(
        self, coro_factory: Callable[[], Coroutine[Any, Any, T]], timeout: float
    ) -> T:
        """Run an async coroutine inside a contained dedicated thread with a private event loop."""
        result_box: list[T] = []
        error_box: list[BaseException] = []

        def _thread_target() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                res = loop.run_until_complete(coro_factory())
                result_box.append(res)
            except BaseException as exc:
                error_box.append(exc)
            finally:
                try:
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass
                loop.close()

        thread = threading.Thread(target=_thread_target, daemon=True)
        thread.start()
        thread.join(timeout=timeout + 5.0)

        if thread.is_alive():
            raise AdapterError(f"MCP execution thread timed out after {timeout:.1f} seconds.")

        if error_box:
            raise error_box[0]

        if not result_box:
            raise AdapterError("MCP execution thread completed without producing a result.")

        return result_box[0]

    async def _execute_async(
        self,
        request: RuntimeRequest,
        payload: dict[str, Any],
        timeout: float,
        start_time: float,
        env: dict[str, str],
    ) -> RuntimeResult:
        """Async implementation using official high-level MCP v2 Client."""
        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=env,
        )

        try:
            async with asyncio.timeout(timeout):
                async with Client(server_params) as client:
                    # Paginate tool discovery to verify configured tool exists
                    tools_res = await client.list_tools()
                    tool_names = [t.name for t in tools_res.tools]
                    cursor = getattr(
                        tools_res, "next_cursor", getattr(tools_res, "nextCursor", None)
                    )
                    while cursor:
                        tools_res = await client.list_tools(cursor=cursor)
                        tool_names.extend([t.name for t in tools_res.tools])
                        cursor = getattr(
                            tools_res, "next_cursor", getattr(tools_res, "nextCursor", None)
                        )

                    if self.tool not in tool_names:
                        execution_ms = (time.perf_counter() - start_time) * 1000.0
                        return RuntimeResult(
                            execution_id=request.execution_id,
                            world_id=request.world_id,
                            status=ExecutionStatus.ADAPTER_ERROR,
                            error_message=(
                                f"Target MCP server does not export configured tool '{self.tool}'. "
                                f"Available tools: {tool_names}"
                            ),
                            execution_time_ms=execution_ms,
                        )

                    # Invoke the configured MCP tool ONCE with canonical request payload
                    res: CallToolResult = await client.call_tool(self.tool, arguments=payload)
                    execution_ms = (time.perf_counter() - start_time) * 1000.0

                    is_err = getattr(res, "is_error", getattr(res, "isError", False))
                    if is_err:
                        err_msg = self._extract_error_text(res)
                        return RuntimeResult(
                            execution_id=request.execution_id,
                            world_id=request.world_id,
                            status=ExecutionStatus.TARGET_ERROR,
                            error_message=f"MCP target tool '{self.tool}' reported an error: {err_msg}",
                            execution_time_ms=execution_ms,
                        )

                    return self._parse_successful_tool_result(
                        request=request,
                        res=res,
                        execution_ms=execution_ms,
                    )

        except (UrlElicitationRequiredError, InputRequiredRoundsExceededError) as exc:
            execution_ms = (time.perf_counter() - start_time) * 1000.0
            return RuntimeResult(
                execution_id=request.execution_id,
                world_id=request.world_id,
                status=ExecutionStatus.UNSUPPORTED_FEATURE,
                error_message=f"MCP target requested an unsupported interactive feature (elicitation/input loop): {exc}",
                execution_time_ms=execution_ms,
            )
        except TimeoutError:
            execution_ms = (time.perf_counter() - start_time) * 1000.0
            return RuntimeResult(
                execution_id=request.execution_id,
                world_id=request.world_id,
                status=ExecutionStatus.TIMEOUT,
                error_message=f"MCP target invocation timed out after {timeout:.1f} seconds",
                execution_time_ms=execution_ms,
            )
        except Exception as exc:
            execution_ms = (time.perf_counter() - start_time) * 1000.0

            def _find_interactive_err(e: BaseException) -> str | None:
                if isinstance(e, (UrlElicitationRequiredError, InputRequiredRoundsExceededError)):
                    return str(e)
                cls_name = type(e).__name__.lower()
                if "elicit" in cls_name or "inputrequired" in cls_name:
                    return str(e)
                if hasattr(e, "exceptions"):
                    for sub in e.exceptions:
                        sub_res = _find_interactive_err(sub)
                        if sub_res is not None:
                            return sub_res
                if "elicitation" in str(e).lower():
                    return str(e)
                return None

            interactive_msg = _find_interactive_err(exc)
            if interactive_msg is not None:
                return RuntimeResult(
                    execution_id=request.execution_id,
                    world_id=request.world_id,
                    status=ExecutionStatus.UNSUPPORTED_FEATURE,
                    error_message=f"MCP target requested an unsupported interactive feature (elicitation/input loop): {interactive_msg}",
                    execution_time_ms=execution_ms,
                )

            msg = str(exc)
            if hasattr(exc, "exceptions"):
                sub_msgs = [str(e) for e in exc.exceptions]
                msg = f"{msg} -> " + "; ".join(sub_msgs)
            return RuntimeResult(
                execution_id=request.execution_id,
                world_id=request.world_id,
                status=ExecutionStatus.ADAPTER_ERROR,
                error_message=f"MCP stdio transport or session error: {msg}",
                execution_time_ms=execution_ms,
            )

    def _extract_error_text(self, res: CallToolResult) -> str:
        """Extract text content from an error CallToolResult."""
        text_parts = []
        for block in res.content:
            if hasattr(block, "text") and block.text:
                text_parts.append(block.text)
            elif isinstance(block, dict) and block.get("text"):
                text_parts.append(str(block.get("text")))
        if text_parts:
            return "\n".join(text_parts)
        return str(res.content)

    def _parse_successful_tool_result(
        self,
        request: RuntimeRequest,
        res: CallToolResult,
        execution_ms: float,
    ) -> RuntimeResult:
        """Parse non-error CallToolResult content according to VIVEKA response contract."""
        raw_text_blocks: list[str] = []

        for block in res.content:
            if hasattr(block, "text") and block.text:
                raw_text_blocks.append(block.text)
            elif isinstance(block, dict) and block.get("text"):
                raw_text_blocks.append(str(block["text"]))
            elif hasattr(block, "model_dump"):
                raw_text_blocks.append(json.dumps(block.model_dump()))

        combined_text = "\n".join(raw_text_blocks)

        # Parse JSON output structure from combined text content
        try:
            data = json.loads(combined_text)
        except Exception:
            return RuntimeResult(
                execution_id=request.execution_id,
                world_id=request.world_id,
                status=ExecutionStatus.ADAPTER_ERROR,
                error_message="MCP tool output text is not valid JSON.",
                execution_time_ms=execution_ms,
            )

        if not isinstance(data, dict):
            return RuntimeResult(
                execution_id=request.execution_id,
                world_id=request.world_id,
                status=ExecutionStatus.ADAPTER_ERROR,
                error_message="MCP tool output JSON must be an object.",
                execution_time_ms=execution_ms,
            )

        events: list[RawEvent] = []
        seq = 1

        # Versioned telemetry contract check
        if "viveka_telemetry" in data:
            telemetry = data["viveka_telemetry"]
            if not isinstance(telemetry, dict):
                return RuntimeResult(
                    execution_id=request.execution_id,
                    world_id=request.world_id,
                    status=ExecutionStatus.ADAPTER_ERROR,
                    error_message="viveka_telemetry must be a JSON object.",
                    execution_time_ms=execution_ms,
                )

            if telemetry.get("schema_version") != 1:
                return RuntimeResult(
                    execution_id=request.execution_id,
                    world_id=request.world_id,
                    status=ExecutionStatus.ADAPTER_ERROR,
                    error_message=f"Unsupported or missing viveka_telemetry schema_version '{telemetry.get('schema_version')}'. Expected schema_version 1.",
                    execution_time_ms=execution_ms,
                )

            if telemetry.get("complete") is not True:
                return RuntimeResult(
                    execution_id=request.execution_id,
                    world_id=request.world_id,
                    status=ExecutionStatus.ADAPTER_ERROR,
                    error_message="viveka_telemetry complete flag is not true.",
                    execution_time_ms=execution_ms,
                )

            ev_list = telemetry.get("events")
            if not isinstance(ev_list, list):
                return RuntimeResult(
                    execution_id=request.execution_id,
                    world_id=request.world_id,
                    status=ExecutionStatus.ADAPTER_ERROR,
                    error_message="viveka_telemetry events field must be a list.",
                    execution_time_ms=execution_ms,
                )

            for ev_dict in ev_list:
                if not isinstance(ev_dict, dict):
                    return RuntimeResult(
                        execution_id=request.execution_id,
                        world_id=request.world_id,
                        status=ExecutionStatus.ADAPTER_ERROR,
                        error_message="Malformed event item in viveka_telemetry events list.",
                        execution_time_ms=execution_ms,
                    )

                ev_type_raw = str(ev_dict.get("event_type", ""))
                try:
                    ev_type = RawEventType(ev_type_raw)
                except ValueError:
                    return RuntimeResult(
                        execution_id=request.execution_id,
                        world_id=request.world_id,
                        status=ExecutionStatus.ADAPTER_ERROR,
                        error_message=f"Invalid event_type '{ev_type_raw}' in viveka_telemetry.",
                        execution_time_ms=execution_ms,
                    )

                event_id = str(ev_dict.get("event_id") or new_id("REVT"))
                raw_event = RawEvent(
                    sequence=seq,
                    event_id=event_id,
                    event_type=ev_type,
                    origin=EventOrigin.TARGET_REPORTED,
                    call_id=ev_dict.get("call_id"),
                    tool_name=ev_dict.get("tool_name"),
                    tool_args=ev_dict.get("tool_args"),
                    tool_result=ev_dict.get("tool_result"),
                    error_message=ev_dict.get("error_message"),
                    output_text=ev_dict.get("output_text"),
                )
                events.append(raw_event)
                seq += 1

        # Strict response output field check
        out_val = data.get("output")
        if not isinstance(out_val, str):
            return RuntimeResult(
                execution_id=request.execution_id,
                world_id=request.world_id,
                status=ExecutionStatus.ADAPTER_ERROR,
                error_message="MCP tool response JSON is missing expected string field 'output'.",
                execution_time_ms=execution_ms,
            )

        output_text = out_val

        # Append final AGENT_OUTPUT event (VIVEKA_OBSERVED) AFTER target-reported events
        events.append(
            RawEvent(
                sequence=seq,
                event_id=new_id("REVT"),
                event_type=RawEventType.AGENT_OUTPUT,
                origin=EventOrigin.VIVEKA_OBSERVED,
                output_text=output_text,
            )
        )

        return RuntimeResult(
            execution_id=request.execution_id,
            world_id=request.world_id,
            status=ExecutionStatus.SUCCESS,
            events=events,
            final_output=output_text,
            execution_time_ms=execution_ms,
        )

    def healthcheck(self) -> bool:
        """Perform healthcheck by opening session and listing tools to verify tool presence.

        Healthcheck ONLY lists tools; it NEVER invokes call_tool(agent.run).
        """
        if not HAS_MCP or not self.command:
            return False

        try:
            return self._run_async_in_contained_thread(self._healthcheck_async, timeout=5.0)
        except Exception:
            return False

    async def _healthcheck_async(self) -> bool:
        """Async implementation of MCP healthcheck."""
        env = {str(k): str(v) for k, v in os.environ.items() if not k.startswith("=")}
        for target_key, host_env_var in self.env_from_host.items():
            secret_val = os.environ.get(host_env_var)
            if secret_val is not None:
                env[target_key] = secret_val

        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=env,
        )

        try:
            async with asyncio.timeout(5.0):
                async with Client(server_params) as client:
                    tools_res = await client.list_tools()
                    tool_names = [t.name for t in tools_res.tools]
                    return self.tool in tool_names
        except Exception:
            return False
