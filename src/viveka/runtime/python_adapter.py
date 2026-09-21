"""
Python Callable Runtime Adapter for VIVEKA Phase 7.

Executes target Python callables in a child process via stdlib `multiprocessing`
to enforce hard execution timeouts (`timeout_seconds`).

Process Isolation Note:
This adapter provides process isolation for hard timeout enforcement (terminating
hung or infinite-loop target child processes). It is NOT a secure OS sandbox.
"""

from __future__ import annotations

import importlib
import time
import warnings
from datetime import UTC, datetime
from multiprocessing import Process, Queue
from typing import TYPE_CHECKING, Any

from viveka.core.errors import VivekaError
from viveka.core.ids import new_id
from viveka.runtime.adapter import BaseRuntimeAdapter
from viveka.runtime.models import (
    RawEvent,
    RuntimeRequest,
    RuntimeResult,
    TargetSpec,
)
from viveka.runtime.vocabulary import ExecutionStatus, RawEventType

if TYPE_CHECKING:
    from collections.abc import Callable


class AdapterError(VivekaError):
    """Raised when an adapter fails to load or execute a target."""


def _child_runner(
    import_path: str,
    request_dict: dict[str, Any],
    result_queue: Queue[tuple[str, list[dict[str, Any]], str | None]],
) -> None:
    """Child process entrypoint for target execution."""
    try:
        req = RuntimeRequest.model_validate(request_dict)
        module_path, func_name = import_path.split(":", 1)
        mod = importlib.import_module(module_path)
        callable_fn: Callable[..., Any] = getattr(mod, func_name)

        # Execute target callable
        out_text, raw_events = callable_fn(req.context, req.seed)

        event_dicts = [e.model_dump(mode="json") for e in raw_events]
        result_queue.put(("success", event_dicts, out_text))
    except Exception as exc:
        result_queue.put(("target_error", [], str(exc)))


class PythonCallableAdapter(BaseRuntimeAdapter):
    """Adapter for executing Python callables in isolated child processes."""

    def __init__(self) -> None:
        self._loaded_spec: TargetSpec | None = None
        self._target_fn: Callable[..., Any] | None = None

    def load_target(self, spec: TargetSpec) -> None:
        """Resolve and validate the target import path."""
        if not spec.import_path or ":" not in spec.import_path:
            raise AdapterError(
                f"Invalid import_path format: '{spec.import_path}'. Expected 'module:function'."
            )
        try:
            module_path, func_name = spec.import_path.split(":", 1)
            mod = importlib.import_module(module_path)
            self._target_fn = getattr(mod, func_name)
            self._loaded_spec = spec
        except (ImportError, AttributeError) as exc:
            raise AdapterError(f"Could not load target from '{spec.import_path}': {exc}") from exc

        warnings.warn(
            "VIVEKA's Python child-process isolation provides timeout/crash containment "
            "but is NOT an OS security sandbox. Target code executes with the current OS user's "
            "permissions. Untrusted targets should be run inside an appropriate container or VM.",
            UserWarning,
            stacklevel=2,
        )

    def healthcheck(self) -> bool:
        """Verify that the target function is loaded and callable."""
        return self._loaded_spec is not None and callable(self._target_fn)

    def execute(self, request: RuntimeRequest) -> RuntimeResult:
        """Execute request in a child process with hard timeout enforcement."""
        spec = request.target
        if not spec.import_path:
            spec = self._loaded_spec or spec

        start_time = time.perf_counter()
        req_dict = request.model_dump(mode="json")

        result_queue: Queue[tuple[str, list[dict[str, Any]], str | None]] = Queue()
        proc = Process(
            target=_child_runner,
            args=(spec.import_path, req_dict, result_queue),
        )

        proc.start()
        proc.join(timeout=request.timeout_seconds)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        if proc.is_alive():
            # Process timed out — force kill
            proc.terminate()
            proc.join(timeout=1.0)
            if proc.is_alive():
                proc.kill()

            timeout_event = RawEvent(
                sequence=1,
                event_id=new_id("VEVT"),
                event_type=RawEventType.RUNTIME_ERROR,
                error_message=f"Execution timed out after {request.timeout_seconds} seconds.",
            )
            return RuntimeResult(
                execution_id=request.execution_id,
                world_id=request.world_id,
                status=ExecutionStatus.TIMEOUT,
                events=[timeout_event],
                final_output="",
                error_message=f"Execution timed out after {request.timeout_seconds} seconds.",
                execution_time_ms=elapsed_ms,
                created_at=datetime.now(UTC),
            )

        # Process finished cleanly or errored
        if not result_queue.empty():
            status_str, event_dicts, payload = result_queue.get()
            events = [RawEvent.model_validate(ed) for ed in event_dicts]

            if status_str == "success":
                return RuntimeResult(
                    execution_id=request.execution_id,
                    world_id=request.world_id,
                    status=ExecutionStatus.SUCCESS,
                    events=events,
                    final_output=payload or "",
                    execution_time_ms=elapsed_ms,
                    created_at=datetime.now(UTC),
                )
            else:
                err_event = RawEvent(
                    sequence=len(events) + 1,
                    event_id=new_id("VEVT"),
                    event_type=RawEventType.RUNTIME_ERROR,
                    error_message=payload or "Target exception",
                )
                return RuntimeResult(
                    execution_id=request.execution_id,
                    world_id=request.world_id,
                    status=ExecutionStatus.TARGET_ERROR,
                    events=[*events, err_event],
                    final_output="",
                    error_message=payload,
                    execution_time_ms=elapsed_ms,
                    created_at=datetime.now(UTC),
                )

        # Exit code non-zero or queue empty
        err_msg = f"Child process exited unexpectedly with code {proc.exitcode}."
        return RuntimeResult(
            execution_id=request.execution_id,
            world_id=request.world_id,
            status=ExecutionStatus.TARGET_ERROR,
            events=[
                RawEvent(
                    sequence=1,
                    event_id=new_id("VEVT"),
                    event_type=RawEventType.RUNTIME_ERROR,
                    error_message=err_msg,
                )
            ],
            final_output="",
            error_message=err_msg,
            execution_time_ms=elapsed_ms,
            created_at=datetime.now(UTC),
        )
