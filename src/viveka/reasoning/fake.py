"""
FakeReasoningProvider for VIVEKA Phase 12 tests.

Returns deterministic canned structured responses without any network calls.
Used in all automated tests to ensure offline operation.
"""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class FakeReasoningProvider:
    """Test provider returning deterministic canned responses.

    Satisfies the ``ReasoningProvider`` protocol without network access.
    """

    def __init__(
        self,
        *,
        model_name: str = "fake-model-v1",
        canned_responses: dict[type, BaseModel] | None = None,
        canned_json: dict[type, dict] | None = None,
    ) -> None:
        self._model_name = model_name
        self._canned_responses: dict[type, BaseModel] = canned_responses or {}
        self._canned_json: dict[type, dict] = canned_json or {}
        self._call_count = 0
        self._call_log: list[dict[str, str]] = []

    @property
    def provider_kind(self) -> str:
        return "fake"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def endpoint_category(self) -> str:
        return "local"

    @property
    def call_count(self) -> int:
        """Number of calls made to this provider."""
        return self._call_count

    @property
    def call_log(self) -> list[dict[str, str]]:
        """Log of all calls made (system_prompt, user_content)."""
        return list(self._call_log)

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
        """Return a canned response for the given schema type.

        Raises:
            ProviderError: If no canned response is registered for the schema.
        """
        from viveka.core.errors import ProviderError

        self._call_count += 1
        self._call_log.append({"system_prompt": system_prompt, "user_content": user_content})

        # Check for pre-built response objects
        if response_schema in self._canned_responses:
            resp = self._canned_responses[response_schema]
            if isinstance(resp, response_schema):
                return resp
            return response_schema.model_validate(resp.model_dump())

        # Check for raw JSON dicts
        if response_schema in self._canned_json:
            return response_schema.model_validate(self._canned_json[response_schema])

        raise ProviderError(
            f"FakeReasoningProvider has no canned response for {response_schema.__name__}.",
            hint="Register a canned response via canned_responses or canned_json.",
        )
