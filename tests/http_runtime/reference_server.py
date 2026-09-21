"""
Reference HTTP test server for VIVEKA Phase 13 offline testing.

Uses standard library http.server to run an in-process HTTP agent server.
Provides zero-cost, offline endpoints for testing normal responses, seed receipt,
versioned telemetry instrumentation, redirects, HTTP 3xx/4xx/5xx status codes,
timeouts, and response schema validation.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


class ReferenceHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the VIVEKA reference test agent."""

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default stderr logging during tests."""
        pass

    def do_GET(self) -> None:
        """Handle GET request (used for healthchecks)."""
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        """Handle POST request from HttpJsonRuntimeAdapter."""
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length)

        path = self.path.split("?")[0]

        # Redirect testing
        if path == "/agent/redirect_302":
            self.send_response(302)
            self.send_header("Location", "/agent")
            self.end_headers()
            self.wfile.write(b'{"message": "Redirecting"}')
            return

        # Error status testing (3xx/4xx/5xx)
        if path == "/agent/error_400":
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "Bad Request"}')
            return

        if path == "/agent/error_401":
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "Unauthorized"}')
            return

        if path == "/agent/error_404":
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "Not Found"}')
            return

        if path == "/agent/error_429":
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "Too Many Requests"}')
            return

        if path == "/agent/error_500":
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "Internal Server Error"}')
            return

        # Response contract failure testing
        if path == "/agent/invalid_json":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"NOT VALID JSON {{{")
            return

        if path == "/agent/missing_output_field":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"wrong_key": "some value"}')
            return

        if path == "/agent/custom_output_field":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"custom_text": "Processed custom field"}')
            return

        if path == "/agent/slow":
            time.sleep(2.0)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"output": "Slow response"}')
            return

        if path == "/agent/oversized":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            huge_str = "x" * (2 * 1024 * 1024)
            self.wfile.write(f'{{"output": "{huge_str}"}}'.encode())
            return

        # Parse request JSON payload
        try:
            req_data = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            req_data = {}

        seed = req_data.get("seed", 0)
        context = req_data.get("context", {})
        message = context.get("message", "")

        # Versioned instrumentation contract endpoints
        if path == "/agent/instrumented":
            resp_data = {
                "output": f"Processed message: '{message}' with seed {seed}",
                "viveka_telemetry": {
                    "schema_version": 1,
                    "complete": True,
                    "events": [
                        {
                            "event_type": "tool_call",
                            "tool_name": "knowledge_search",
                            "tool_args": {"query": message},
                            "call_id": "call-101",
                        },
                        {
                            "event_type": "tool_result",
                            "tool_name": "knowledge_search",
                            "tool_result": "Search results found",
                            "call_id": "call-101",
                        },
                    ],
                },
            }
        elif path == "/agent/instrumented_unsupported_version":
            resp_data = {
                "output": "Output text",
                "viveka_telemetry": {
                    "schema_version": 99,
                    "complete": True,
                    "events": [],
                },
            }
        elif path == "/agent/instrumented_incomplete":
            resp_data = {
                "output": "Output text",
                "viveka_telemetry": {
                    "schema_version": 1,
                    "complete": False,
                    "events": [],
                },
            }
        elif path == "/agent/instrumented_invalid_event":
            resp_data = {
                "output": "Output text",
                "viveka_telemetry": {
                    "schema_version": 1,
                    "complete": True,
                    "events": [{"event_type": "magic_unsupported_event"}],
                },
            }
        elif path == "/agent/instrumented_malformed":
            resp_data = {
                "output": "Output text",
                "viveka_telemetry": {
                    "schema_version": 1,
                    "complete": True,
                    "events": "not a list",
                },
            }
        else:
            resp_data = {
                "output": f"Processed message: '{message}' with seed {seed}",
                "execution_id": req_data.get("execution_id"),
            }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(resp_data).encode("utf-8"))


class ReferenceHTTPServer:
    """Threaded wrapper around HTTPServer for integration testing."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.server = HTTPServer((host, port), ReferenceHTTPHandler)
        self.host, self.port = self.server.server_address
        self.endpoint_url = f"http://{self.host}:{self.port}/agent"
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start server in background thread."""
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop server and release socket."""
        self.server.shutdown()
        self.server.server_close()
        if self._thread:
            self._thread.join(timeout=2.0)
