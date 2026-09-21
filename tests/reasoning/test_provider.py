"""
Unit tests for ReasoningProvider protocol, factory, and config resolution.
"""

from __future__ import annotations

import pytest

from viveka.core.config import (
    ProviderConfig,
    ReasoningConfig,
    VivekaConfig,
)
from viveka.core.errors import ConfigurationError, ProviderError
from viveka.reasoning.factory import create_provider, is_local_endpoint
from viveka.reasoning.fake import FakeReasoningProvider
from viveka.reasoning.provider import ReasoningProvider
from viveka.reasoning.schemas import AdvisoryDiagnosisNarrative, PropertyProposalList


def test_is_local_endpoint_classification() -> None:
    assert is_local_endpoint("http://localhost:11434") is True
    assert is_local_endpoint("http://127.0.0.1:8000") is True
    assert is_local_endpoint("http://[::1]:11434") is True
    assert is_local_endpoint("http://::1:11434") is True
    assert is_local_endpoint("http://127.0.0.5:11434") is True
    assert is_local_endpoint("http://0.0.0.0:8000") is True
    assert is_local_endpoint("https://api.openai.com/v1") is False
    assert is_local_endpoint("http://192.168.1.100:11434") is False
    assert is_local_endpoint("https://my-model-host.internal/v1") is False


def test_none_mode_returns_none() -> None:
    cfg = VivekaConfig(
        reasoning=ReasoningConfig(
            mode="none",
            provider=ProviderConfig(type="ollama"),
        )
    )
    provider = create_provider(cfg)
    assert provider is None


def test_ollama_local_config_resolution() -> None:
    cfg = VivekaConfig(
        reasoning=ReasoningConfig(
            mode="enabled",
            provider=ProviderConfig(type="ollama", model="llama3.2:3b"),
        )
    )
    provider = create_provider(cfg)
    assert provider is not None
    assert isinstance(provider, ReasoningProvider)
    assert provider.provider_kind == "ollama"
    assert provider.model_name == "llama3.2:3b"
    assert provider.endpoint_category == "local"


def test_ollama_remote_blocked_without_permission() -> None:
    cfg = VivekaConfig(
        reasoning=ReasoningConfig(
            mode="enabled",
            provider=ProviderConfig(
                type="ollama",
                model="llama3.2:3b",
                base_url="http://remote-gpu-box:11434",
            ),
            allow_remote_reasoning=False,
        )
    )
    with pytest.raises(ConfigurationError, match="Remote reasoning is disabled"):
        create_provider(cfg)


def test_ollama_remote_allowed_with_permission() -> None:
    cfg = VivekaConfig(
        reasoning=ReasoningConfig(
            mode="enabled",
            provider=ProviderConfig(
                type="ollama",
                model="llama3.2:3b",
                base_url="http://remote-gpu-box:11434",
            ),
            allow_remote_reasoning=True,
        )
    )
    provider = create_provider(cfg)
    assert provider is not None
    assert provider.endpoint_category == "remote"


def test_ollama_missing_model_raises() -> None:
    cfg = VivekaConfig(
        reasoning=ReasoningConfig(
            mode="enabled",
            provider=ProviderConfig(type="ollama", model=None),
        )
    )
    with pytest.raises(ConfigurationError, match="requires a model name"):
        create_provider(cfg)


def test_openai_compatible_local_config_resolution() -> None:
    cfg = VivekaConfig(
        reasoning=ReasoningConfig(
            mode="enabled",
            provider=ProviderConfig(
                type="openai-compatible",
                model="deepseek-r1",
                base_url="http://localhost:8000/v1",
                api_key_env="LOCAL_KEY",
            ),
        )
    )
    provider = create_provider(cfg)
    assert provider is not None
    assert provider.provider_kind == "openai_compatible"
    assert provider.model_name == "deepseek-r1"
    assert provider.endpoint_category == "local"


def test_openai_compatible_missing_base_url_raises() -> None:
    cfg = VivekaConfig(
        reasoning=ReasoningConfig(
            mode="enabled",
            provider=ProviderConfig(
                type="openai-compatible",
                model="gpt-4o",
                base_url=None,
            ),
        )
    )
    with pytest.raises(ConfigurationError, match="requires base_url"):
        create_provider(cfg)


def test_openai_compatible_remote_blocked_by_default() -> None:
    cfg = VivekaConfig(
        reasoning=ReasoningConfig(
            mode="enabled",
            provider=ProviderConfig(
                type="openai-compatible",
                model="gpt-4o-mini",
                base_url="https://api.openai.com/v1",
            ),
            allow_remote_reasoning=False,
        ),
    )
    with pytest.raises(ConfigurationError, match="Remote reasoning is disabled"):
        create_provider(cfg)


def test_openai_compatible_remote_allowed_when_opted_in() -> None:
    cfg = VivekaConfig(
        reasoning=ReasoningConfig(
            mode="enabled",
            provider=ProviderConfig(
                type="openai-compatible",
                model="gpt-4o-mini",
                base_url="https://api.openai.com/v1",
            ),
            allow_remote_reasoning=True,
        ),
    )
    provider = create_provider(cfg)
    assert provider is not None
    assert provider.endpoint_category == "remote"


def test_fake_provider_satisfies_protocol() -> None:
    canned = AdvisoryDiagnosisNarrative(narrative="Test narrative")
    fake = FakeReasoningProvider(canned_responses={AdvisoryDiagnosisNarrative: canned})
    assert isinstance(fake, ReasoningProvider)
    assert fake.provider_kind == "fake"
    assert fake.call_count == 0

    res = fake.generate_structured("system", "user", AdvisoryDiagnosisNarrative)
    assert res.narrative == "Test narrative"
    assert fake.call_count == 1
    assert len(fake.call_log) == 1


def test_fake_provider_missing_response_raises() -> None:
    fake = FakeReasoningProvider()
    with pytest.raises(ProviderError, match="no canned response"):
        fake.generate_structured("sys", "usr", PropertyProposalList)
