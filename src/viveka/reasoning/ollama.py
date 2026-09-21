"""
Ollama reasoning provider for VIVEKA Phase 12.

Connects to a local Ollama instance (default: http://localhost:11434)
using structured JSON format mode.
"""

from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel

from viveka.core.errors import ProviderError

T = TypeVar("T", bound=BaseModel)


class OllamaProvider:
    """Ollama reasoning provider using local HTTP API."""

    def __init__(
        self,
        *,
        model: str,
        base_url: str = "http://localhost:11434",
        is_remote: bool = False,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._is_remote = is_remote

    @property
    def provider_kind(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def endpoint_category(self) -> str:
        return "remote" if self._is_remote else "local"

    def generate_structured(
        self,
        system_prompt: str,
        user_content: str,
        response_schema: type[T],
        *,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout_seconds: float = 60.0,
    ) -> T:
        """Call Ollama /api/chat with format="json" and validate output against response_schema."""
        try:
            import httpx
        except ImportError as exc:
            raise ProviderError(
                "The 'httpx' package is required for Ollama reasoning. "
                "Install it with: pip install 'viveka-engine[reasoning]' or pip install httpx",
                hint="Install httpx or set reasoning.mode: deterministic",
            ) from exc

        endpoint = f"{self._base_url}/api/chat"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.post(endpoint, json=payload)
        except httpx.ConnectError as exc:
            raise ProviderError(
                f"Ollama is not reachable at '{self._base_url}'. "
                "Ensure Ollama is running (`ollama serve`).",
                hint="Start Ollama locally or switch reasoning.mode to deterministic.",
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderError(
                f"Ollama request timed out after {timeout_seconds}s.",
                hint="Increase timeout in config or use a smaller/faster local model.",
            ) from exc
        except Exception as exc:
            raise ProviderError(
                f"HTTP request to Ollama failed: {exc}",
                hint="Check local Ollama server logs.",
            ) from exc

        if response.status_code == 404:
            raise ProviderError(
                f"Model '{self._model}' not found in Ollama at '{self._base_url}'.",
                hint=f"Run `ollama pull {self._model}` or check the model name in config.",
            )
        if response.is_error:
            raise ProviderError(
                f"Ollama returned HTTP {response.status_code}: {response.text}",
                hint="Check Ollama logs for details.",
            )

        try:
            data = response.json()
            message_content = data.get("message", {}).get("content", "")
            raw_parsed = json.loads(message_content)
        except Exception as exc:
            raise ProviderError(
                f"Failed to parse JSON response from Ollama: {exc}",
                hint="Ensure the local model supports structured JSON output.",
            ) from exc

        try:
            return response_schema.model_validate(raw_parsed)
        except Exception as exc:
            raise ProviderError(
                f"Ollama output did not match expected schema '{response_schema.__name__}': {exc}",
                hint="The model output was missing required fields or had invalid types.",
            ) from exc
