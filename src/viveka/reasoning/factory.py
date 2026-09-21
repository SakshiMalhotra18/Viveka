"""
Factory for creating ReasoningProvider instances from VIVEKA configuration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from viveka.core.errors import ConfigurationError
from viveka.reasoning.ollama import OllamaProvider
from viveka.reasoning.openai_compat import OpenAICompatibleProvider
from viveka.reasoning.provider import ReasoningProvider

if TYPE_CHECKING:
    from viveka.core.config import VivekaConfig


def is_local_endpoint(url: str) -> bool:
    """Determine whether an endpoint URL points to the local machine.

    Local hostnames: localhost, 127.0.0.1, ::1, 0.0.0.0, or 127.x.x.x.
    All other hostnames are treated as remote endpoints.
    """
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().strip("[]")
        if not host and parsed.netloc:
            netloc = parsed.netloc.strip("[]")
            if netloc.startswith("::1"):
                host = "::1"
            elif ":" in netloc:
                host = netloc.split(":")[0].lower().strip("[]")
            else:
                host = netloc.lower()
        if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or host.startswith("127."):
            return True
        return False
    except Exception:
        return False


def create_provider(config: VivekaConfig) -> ReasoningProvider | None:
    """Create a ReasoningProvider according to VivekaConfig.

    Returns:
        A ReasoningProvider instance, or None if reasoning.mode is "none".

    Raises:
        ConfigurationError: If the configuration is invalid, missing required settings,
            or references a remote endpoint without explicit allow_remote_reasoning.
    """
    mode = config.reasoning.mode
    if mode == "none":
        return None

    prov_cfg = config.reasoning.provider

    if prov_cfg.type == "ollama":
        if not prov_cfg.model:
            raise ConfigurationError(
                "Ollama provider requires a model name (reasoning.provider.model).",
                hint="Specify a model like 'llama3.2:3b' in .viveka/config.yaml.",
            )
        base_url = prov_cfg.base_url or "http://localhost:11434"
        is_local = is_local_endpoint(base_url)

        if not is_local and not config.reasoning.allow_remote_reasoning:
            raise ConfigurationError(
                f"Remote reasoning is disabled (reasoning.allow_remote_reasoning is false). "
                f"The configured Ollama endpoint '{base_url}' is not a local host.",
                hint="Set reasoning.allow_remote_reasoning: true in .viveka/config.yaml to allow remote endpoints.",
            )

        return OllamaProvider(
            model=prov_cfg.model,
            base_url=base_url,
            is_remote=not is_local,
        )

    elif prov_cfg.type == "openai-compatible":
        if not prov_cfg.model:
            raise ConfigurationError(
                "OpenAI-compatible provider requires a model name (reasoning.provider.model).",
                hint="Set reasoning.provider.model in .viveka/config.yaml.",
            )
        if not prov_cfg.base_url:
            raise ConfigurationError(
                "OpenAI-compatible provider requires base_url (reasoning.provider.base_url).",
                hint="Set reasoning.provider.base_url in .viveka/config.yaml.",
            )

        is_local = is_local_endpoint(prov_cfg.base_url)

        if not is_local and not config.reasoning.allow_remote_reasoning:
            raise ConfigurationError(
                f"Remote reasoning is disabled (reasoning.allow_remote_reasoning is false). "
                f"The configured OpenAI-compatible endpoint '{prov_cfg.base_url}' is not a local host.",
                hint="Set reasoning.allow_remote_reasoning: true in .viveka/config.yaml to allow remote endpoints.",
            )

        return OpenAICompatibleProvider(
            model=prov_cfg.model,
            base_url=prov_cfg.base_url,
            api_key_env=prov_cfg.api_key_env,
            is_remote=not is_local,
        )

    else:
        raise ConfigurationError(
            f"Unsupported provider type '{prov_cfg.type}'.",
            hint="Supported types: 'ollama', 'openai-compatible'.",
        )
