"""
VIVEKA Phase 13: Generic HTTP / JSON Runtime Adapter.

Provides HttpJsonRuntimeAdapter for executing target agents exposed over HTTP/JSON APIs.
Features strict POST execution, zero automatic redirects, host classification,
bounded response reading, versioned telemetry contract, and evidence-preserving provenance.
"""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from viveka.core.ids import new_id
from viveka.runtime.adapter import BaseRuntimeAdapter
from viveka.runtime.models import RawEvent, RuntimeRequest, RuntimeResult, TargetSpec
from viveka.runtime.python_adapter import AdapterError
from viveka.runtime.vocabulary import EventOrigin, ExecutionStatus, RawEventType


def is_local_target_endpoint(url: str) -> bool:
    """Classify whether an HTTP target URL points to a local host.

    Local hosts include: localhost, 127.0.0.0/8 loopback, ::1.
    0.0.0.0 and wildcard addresses are explicitly REJECTED as valid local execution targets.
    """
    try:
        parsed = urllib.parse.urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if not hostname or hostname in ("0.0.0.0", "::", "0:0:0:0:0:0:0:0"):
            return False
        if (
            hostname == "localhost"
            or hostname == "::1"
            or hostname.startswith("127.")
            or hostname.endswith(".local")
        ):
            return True
        try:
            ip = ipaddress.ip_address(hostname)
            return ip.is_loopback
        except ValueError:
            return False
    except Exception:
        return False


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Custom HTTP redirect handler that prevents following any automatic redirects."""

    def redirect_request(  # type: ignore[override]
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        # Returning None prevents following redirects and surfaces 3xx status directly to caller
        return None


class HttpJsonRuntimeAdapter(BaseRuntimeAdapter):
    """Runtime adapter for invoking target agents over an HTTP/JSON interface."""

    def __init__(self) -> None:
        self.endpoint: str = ""
        self.healthcheck_url: str | None = None
        self.method: str = "POST"
        self.timeout_seconds: float = 30.0
        self.allow_remote_target: bool = False
        self.auth_header_env: str | None = None
        self.max_response_bytes: int = 1_048_576  # 1 MB default
        self.response_output_field: str = "output"
        self._target_spec: TargetSpec | None = None

    def load_target(self, spec: TargetSpec) -> None:
        """Load and validate the HTTP target specification."""
        self._target_spec = spec
        opts = spec.options or {}

        # Endpoint URL from spec.endpoint or spec.import_path or options['endpoint']
        endpoint = (spec.endpoint or spec.import_path or opts.get("endpoint", "")).strip()
        if not endpoint:
            raise AdapterError(
                "HTTP target spec requires a valid endpoint URL in spec.endpoint or options['endpoint']."
            )

        parsed = urllib.parse.urlparse(endpoint)
        if parsed.scheme not in ("http", "https"):
            raise AdapterError(
                f"Unsupported URL scheme '{parsed.scheme}' for HTTP target '{endpoint}'. "
                "Only 'http' and 'https' schemes are supported."
            )

        hostname = (parsed.hostname or "").lower()
        if hostname in ("0.0.0.0", "::", "0:0:0:0:0:0:0:0"):
            raise AdapterError(
                f"HTTP target endpoint '{endpoint}' uses destination address '{hostname}', "
                "which is invalid as an execution target address."
            )

        self.endpoint = endpoint
        self.healthcheck_url = opts.get("healthcheck")
        self.method = "POST"  # Execution is POST-only in Phase 13 V1
        self.auth_header_env = opts.get("auth_header_env")
        self.response_output_field = opts.get("response_output_field", "output")

        try:
            self.timeout_seconds = float(opts.get("timeout_seconds", 30.0))
        except ValueError:
            self.timeout_seconds = 30.0

        try:
            self.max_response_bytes = int(opts.get("max_response_bytes", 1_048_576))
        except ValueError:
            self.max_response_bytes = 1_048_576

        allow_remote_str = str(opts.get("allow_remote_target", "false")).lower()
        self.allow_remote_target = allow_remote_str in ("true", "1", "yes")

        # Remote target enforcement
        if not is_local_target_endpoint(self.endpoint) and not self.allow_remote_target:
            raise AdapterError(
                f"HTTP target endpoint '{self.endpoint}' resolves to a remote host, "
                "which requires explicit opt-in (set allow_remote_target: true)."
            )

    def execute(self, request: RuntimeRequest) -> RuntimeResult:
        """Execute a single trial run against the HTTP target agent."""
        if not self.endpoint:
            raise AdapterError(
                "HttpJsonRuntimeAdapter.load_target() must be called before execute()."
            )

        timeout = request.timeout_seconds if request.timeout_seconds > 0 else self.timeout_seconds
        start_time = time.perf_counter()

        payload = {
            "execution_id": request.execution_id,
            "world_id": request.world_id,
            "seed": request.seed,
            "context": request.context.model_dump(mode="json"),
        }

        try:
            data_bytes = json.dumps(payload, indent=None).encode("utf-8")
        except Exception as exc:
            return RuntimeResult(
                execution_id=request.execution_id,
                world_id=request.world_id,
                status=ExecutionStatus.ADAPTER_ERROR,
                error_message=f"Failed to serialize RuntimeRequest payload to JSON: {exc}",
                execution_time_ms=(time.perf_counter() - start_time) * 1000.0,
            )

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "VIVEKA-Engine/0.1.0",
        }

        if self.auth_header_env:
            token = os.environ.get(self.auth_header_env)
            if token:
                headers["Authorization"] = f"Bearer {token}"

        req = urllib.request.Request(
            url=self.endpoint,
            data=data_bytes,
            headers=headers,
            method="POST",
        )

        ssl_ctx = ssl.create_default_context()
        opener = urllib.request.build_opener(
            NoRedirectHandler(), urllib.request.HTTPSHandler(context=ssl_ctx)
        )

        try:
            with opener.open(req, timeout=timeout) as resp:
                status_code = resp.status

                # If status is non-2xx (e.g. 3xx redirect surfaced without exception)
                if status_code < 200 or status_code >= 300:
                    execution_ms = (time.perf_counter() - start_time) * 1000.0
                    return RuntimeResult(
                        execution_id=request.execution_id,
                        world_id=request.world_id,
                        status=ExecutionStatus.TARGET_ERROR,
                        error_message=f"HTTP target returned non-2xx status code {status_code}",
                        execution_time_ms=execution_ms,
                    )

                body_bytes = self._read_bounded_body(resp, self.max_response_bytes)
                execution_ms = (time.perf_counter() - start_time) * 1000.0

                return self._parse_successful_response(
                    request=request,
                    body_bytes=body_bytes,
                    status_code=status_code,
                    execution_ms=execution_ms,
                )

        except urllib.error.HTTPError as exc:
            execution_ms = (time.perf_counter() - start_time) * 1000.0
            # Any valid HTTP status code received from target (3xx, 4xx, 5xx) is TARGET_ERROR
            return RuntimeResult(
                execution_id=request.execution_id,
                world_id=request.world_id,
                status=ExecutionStatus.TARGET_ERROR,
                error_message=f"HTTP target returned status {exc.code} {exc.reason}",
                execution_time_ms=execution_ms,
            )

        except (urllib.error.URLError, TimeoutError) as exc:
            execution_ms = (time.perf_counter() - start_time) * 1000.0
            reason_str = str(getattr(exc, "reason", exc))
            if "timed out" in reason_str.lower() or isinstance(exc, (socket.timeout, TimeoutError)):
                return RuntimeResult(
                    execution_id=request.execution_id,
                    world_id=request.world_id,
                    status=ExecutionStatus.TIMEOUT,
                    error_message=f"HTTP request timed out after {timeout:.1f} seconds",
                    execution_time_ms=execution_ms,
                )
            return RuntimeResult(
                execution_id=request.execution_id,
                world_id=request.world_id,
                status=ExecutionStatus.ADAPTER_ERROR,
                error_message=f"HTTP connection failed to endpoint '{self.endpoint}': {reason_str}",
                execution_time_ms=execution_ms,
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
                error_message=f"Unexpected error executing HTTP request: {exc}",
                execution_time_ms=execution_ms,
            )

    def healthcheck(self) -> bool:
        """Perform lightweight healthcheck (GET-only) against healthcheck endpoint."""
        url = self.healthcheck_url or self.endpoint
        if not url:
            return False
        try:
            req = urllib.request.Request(url=url, method="GET")
            ssl_ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=5.0, context=ssl_ctx) as resp:
                return 200 <= resp.status < 400
        except Exception:
            return False

    def _read_bounded_body(self, response: Any, max_bytes: int) -> bytes:
        """Read response stream in chunks enforcing max_bytes limit."""
        chunks: list[bytes] = []
        total_read = 0
        chunk_size = 65536

        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            total_read += len(chunk)
            if total_read > max_bytes:
                raise AdapterError(f"HTTP response body exceeded max limit of {max_bytes} bytes.")
            chunks.append(chunk)

        return b"".join(chunks)

    def _parse_successful_response(
        self,
        request: RuntimeRequest,
        body_bytes: bytes,
        status_code: int,
        execution_ms: float,
    ) -> RuntimeResult:
        """Parse HTTP 2xx response body according to strict Phase 13 response contract."""
        body_text = body_bytes.decode("utf-8", errors="replace")

        try:
            data = json.loads(body_text)
        except Exception:
            return RuntimeResult(
                execution_id=request.execution_id,
                world_id=request.world_id,
                status=ExecutionStatus.ADAPTER_ERROR,
                error_message="HTTP response body is not valid JSON.",
                execution_time_ms=execution_ms,
            )

        if not isinstance(data, dict):
            return RuntimeResult(
                execution_id=request.execution_id,
                world_id=request.world_id,
                status=ExecutionStatus.ADAPTER_ERROR,
                error_message="HTTP response body must be a JSON object.",
                execution_time_ms=execution_ms,
            )

        events: list[RawEvent] = []
        seq = 1

        # Versioned instrumentation contract check
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

        # Strict response output field check (no guessing)
        out_val = data.get(self.response_output_field)
        if not isinstance(out_val, str):
            return RuntimeResult(
                execution_id=request.execution_id,
                world_id=request.world_id,
                status=ExecutionStatus.ADAPTER_ERROR,
                error_message=f"HTTP response JSON is missing expected string field '{self.response_output_field}'.",
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
