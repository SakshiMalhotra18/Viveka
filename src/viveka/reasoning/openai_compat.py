"""
OpenAI-compatible reasoning provider for VIVEKA Phase 12.

Connects to any generic OpenAI-compatible chat completions endpoint
(e.g., vLLM, LocalAI, LM Studio, or user-configured hosted endpoint).
"""

from __future__ import annotations

import json
import os
from typing import TypeVar

from pydantic import BaseModel

from viveka.core.errors import ProviderError

T = TypeVar("T", bound=BaseModel)


class OpenAICompatibleProvider:
    """Generic OpenAI-compatible HTTP chat completions provider."""

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        api_key_env: str | None = None,
        is_remote: bool = False,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._api_key_env = api_key_env
        self._is_remote = is_remote

    @property
    def provider_kind(self) -> str:
        return "openai_compatible"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def endpoint_category(self) -> str:
        return "remote" if self._is_remote else "local"

    def _get_api_key(self) -> str | None:
        if not self._api_key_env:
            return None
        return os.getenv(self._api_key_env)

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
        """Call {base_url}/chat/completions with response_format json_object and validate output."""
        try:
            import httpx
        except ImportError as exc:
            raise ProviderError(
                "The 'httpx' package is required for OpenAI-compatible reasoning. "
                "Install it with: pip install 'viveka-engine[reasoning]' or pip install httpx",
                hint="Install httpx or set reasoning.mode: deterministic",
            ) from exc

        endpoint = f"{self._base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        api_key = self._get_api_key()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                response = client.post(endpoint, headers=headers, json=payload)
        except httpx.ConnectError as exc:
            raise ProviderError(
                f"Cannot connect to OpenAI-compatible endpoint at '{self._base_url}'.",
                hint="Verify the server is running and base_url is correct.",
            ) from exc
        except httpx.TimeoutException as exc:
            raise ProviderError(
                f"Request to '{self._base_url}' timed out after {timeout_seconds}s.",
                hint="Increase timeout or check endpoint performance.",
            ) from exc
        except Exception as exc:
            raise ProviderError(
                f"HTTP request to '{self._base_url}' failed: {exc}",
                hint="Check network connection and endpoint configuration.",
            ) from exc

        if response.status_code in (401, 403):
            raise ProviderError(
                f"Authentication failed at '{self._base_url}' (HTTP {response.status_code}).",
                hint=(
                    f"Check the environment variable '{self._api_key_env}' or endpoint credentials."
                    if self._api_key_env
                    else "Endpoint requires authentication. Configure api_key_env."
                ),
            )
        if response.is_error:
            raise ProviderError(
                f"Endpoint returned HTTP {response.status_code}: {response.text}",
                hint="Check provider documentation and logs.",
            )

        try:
            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("No choices in model response")
            content_str = choices[0].get("message", {}).get("content", "")
            raw_parsed = json.loads(content_str)
        except Exception as exc:
            raise ProviderError(
                f"Failed to parse JSON response from '{self._base_url}': {exc}",
                hint="Ensure model returns valid JSON conforming to the schema.",
            ) from exc

        try:
            return response_schema.model_validate(raw_parsed)
        except Exception as exc:
            raise ProviderError(
                f"Output from '{self._base_url}' did not match schema '{response_schema.__name__}': {exc}",
                hint="Check that the model follows schema instructions.",
            ) from exc
