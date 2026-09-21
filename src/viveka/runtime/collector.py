"""
VIVEKA-owned EventCollector and tool wrappers.

Target agent callables do NOT manufacture RawEvent objects.
Instead, VIVEKA wraps tools with an EventCollector that intercepts calls and
emits RawEvent telemetry with monotonically increasing sequence numbers and
call correlation UUIDs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from viveka.core.ids import new_id
from viveka.runtime.models import RawEvent
from viveka.runtime.vocabulary import RawEventType

if TYPE_CHECKING:
    from collections.abc import Callable


class EventCollector:
    """Thread-safe / process-safe event collector for a single execution run."""

    def __init__(self) -> None:
        self._events: list[RawEvent] = []
        self._sequence: int = 0

    @property
    def events(self) -> list[RawEvent]:
        return list(self._events)

    def record_tool_call(self, tool_name: str, args: dict[str, Any]) -> str:
        """Record a TOOL_CALL event and return a unique call_id (UUID)."""
        self._sequence += 1
        call_id = str(uuid4())
        evt = RawEvent(
            sequence=self._sequence,
            event_id=new_id("VEVT"),
            event_type=RawEventType.TOOL_CALL,
            call_id=call_id,
            tool_name=tool_name,
            tool_args=args,
        )
        self._events.append(evt)
        return call_id

    def record_tool_result(
        self,
        call_id: str,
        tool_name: str,
        result: Any | None = None,
        error_message: str | None = None,
    ) -> None:
        """Record a TOOL_RESULT event correlated with *call_id*."""
        self._sequence += 1
        evt = RawEvent(
            sequence=self._sequence,
            event_id=new_id("VEVT"),
            event_type=RawEventType.TOOL_RESULT,
            call_id=call_id,
            tool_name=tool_name,
            tool_result=result,
            error_message=error_message,
        )
        self._events.append(evt)

    def record_agent_output(self, text: str) -> None:
        """Record an AGENT_OUTPUT event."""
        self._sequence += 1
        evt = RawEvent(
            sequence=self._sequence,
            event_id=new_id("VEVT"),
            event_type=RawEventType.AGENT_OUTPUT,
            output_text=text,
        )
        self._events.append(evt)

    def record_runtime_error(self, error_message: str) -> None:
        """Record a RUNTIME_ERROR event."""
        self._sequence += 1
        evt = RawEvent(
            sequence=self._sequence,
            event_id=new_id("VEVT"),
            event_type=RawEventType.RUNTIME_ERROR,
            error_message=error_message,
        )
        self._events.append(evt)


def wrap_tool(
    name: str,
    func: Callable[..., Any],
    collector: EventCollector,
) -> Callable[..., Any]:
    """Wrap a tool function to emit RawEvent telemetry into *collector*."""

    def _wrapped(**kwargs: Any) -> Any:
        call_id = collector.record_tool_call(name, kwargs)
        try:
            res = func(**kwargs)
            collector.record_tool_result(call_id, name, result=res)
            return res
        except Exception as exc:
            collector.record_tool_result(call_id, name, error_message=str(exc))
            raise

    return _wrapped
