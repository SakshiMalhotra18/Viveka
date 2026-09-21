"""
ReasoningProvider protocol for VIVEKA Phase 12.

Defines the minimal interface that all reasoning providers must satisfy.
This is structured model inference only — no tools, agents, chains, memory,
or autonomous loops.
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class ReasoningProvider(Protocol):
    """Minimal structured-inference interface for VIVEKA advisory reasoning.

    Implementations must parse model responses into validated Pydantic models.
    On failure, implementations raise ``ProviderError``.
    """

    @property
    def provider_kind(self) -> str:
        """Provider type identifier (e.g. 'ollama', 'openai_compatible', 'fake')."""
        ...

    @property
    def model_name(self) -> str:
        """Model name string (e.g. 'llama3.2:3b', 'gpt-4o-mini')."""
        ...

    @property
    def endpoint_category(self) -> str:
        """Endpoint locality: 'local' or 'remote'."""
        ...

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
        """Generate a structured response matching the given Pydantic schema.

        Args:
            system_prompt: System-level instructions for the model.
            user_content: User-level content (may contain untrusted data).
            response_schema: Pydantic model class to validate the response against.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.
            timeout_seconds: Request timeout.

        Returns:
            A validated instance of ``response_schema``.

        Raises:
            ProviderError: On network failure, parse failure, or validation failure.
        """
        ...
