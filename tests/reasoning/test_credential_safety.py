"""
Focused test verifying credential safety and secret sanitization across Phase 12.
"""

from __future__ import annotations

import os

from viveka.core.config import ProviderConfig, ReasoningConfig, VivekaConfig
from viveka.core.errors import ProviderError
from viveka.reasoning.openai_compat import OpenAICompatibleProvider
from viveka.reasoning.schemas import ReasoningProvenance


def test_credential_is_never_leaked_in_provenance_config_or_errors() -> None:
    secret_key = "sk-super-secret-key-xyz-123456789"
    env_var_name = "VIVEKA_TEST_SECRET_KEY"
    os.environ[env_var_name] = secret_key

    try:
        # 1. Config serialization only stores the env var name, never the secret
        prov_cfg = ProviderConfig(
            type="openai-compatible",
            model="test-model",
            base_url="http://localhost:8000/v1",
            api_key_env=env_var_name,
        )
        cfg = VivekaConfig(reasoning=ReasoningConfig(mode="enabled", provider=prov_cfg))
        dumped_cfg = cfg.model_dump(mode="json")
        cfg_str = str(dumped_cfg)
        assert secret_key not in cfg_str
        assert env_var_name in cfg_str

        # 2. Provenance contains no secrets
        prov = ReasoningProvenance(
            provider_kind="openai_compatible",
            model="test-model",
            endpoint_category="local",
        )
        dumped_prov = prov.model_dump(mode="json")
        prov_str = str(dumped_prov)
        assert secret_key not in prov_str
        assert "api_key" not in dumped_prov

        # 3. Provider error messages never leak the raw API key value
        provider = OpenAICompatibleProvider(
            model="test-model",
            base_url="http://localhost:54321/v1",  # unreachable port
            api_key_env=env_var_name,
        )

        try:
            # Attempt call against unreachable port to trigger error
            provider.generate_structured("sys", "usr", ReasoningProvenance, timeout_seconds=0.5)
        except ProviderError as exc:
            error_msg = str(exc)
            hint_msg = str(exc.hint or "")
            assert secret_key not in error_msg
            assert secret_key not in hint_msg
    finally:
        os.environ.pop(env_var_name, None)
