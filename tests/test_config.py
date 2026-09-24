"""Tests for viveka.core.config."""

from __future__ import annotations

import textwrap
import warnings
from pathlib import Path

import pytest

from viveka.core.config import VivekaConfig, load_config, write_default_config
from viveka.core.errors import ConfigurationError


class TestLoadConfig:
    def test_load_default_written_config(self, tmp_path: Path) -> None:
        """A config written by write_default_config must load and validate cleanly."""
        cfg_path = tmp_path / "config.yaml"
        write_default_config(cfg_path)
        cfg = load_config(cfg_path)
        assert isinstance(cfg, VivekaConfig)
        assert cfg.version == 1

    def test_missing_file_raises_configuration_error(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigurationError, match="not found"):
            load_config(tmp_path / "nonexistent.yaml")

    def test_invalid_yaml_raises_configuration_error(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text("version: [\nbad yaml", encoding="utf-8")
        with pytest.raises(ConfigurationError):
            load_config(cfg_path)

    def test_unsupported_version_raises(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text("version: 99\n", encoding="utf-8")
        with pytest.raises(ConfigurationError, match="Unsupported"):
            load_config(cfg_path)

    def test_defaults_are_safe(self, tmp_path: Path) -> None:
        """Minimal YAML must produce safe, privacy-preserving defaults."""
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text("version: 1\n", encoding="utf-8")
        cfg = load_config(cfg_path)
        # Privacy defaults — nothing leaves the machine
        assert cfg.privacy.allow_cloud_reasoning is False
        assert cfg.privacy.send_source_code is False
        assert cfg.privacy.send_trace_content is False
        assert cfg.privacy.redact_secrets is True
        # Paid fallback must be off
        assert cfg.reasoning.paid_fallback is False

    def test_paid_fallback_true_emits_warning(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(
            textwrap.dedent("""\
                version: 1
                reasoning:
                  mode: enabled
                  paid_fallback: true
                  provider:
                    type: ollama
                    model: qwen3
            """),
            encoding="utf-8",
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cfg = load_config(cfg_path)
        assert cfg.reasoning.paid_fallback is True
        assert any("paid_fallback" in str(w.message) for w in caught)

    def test_invalid_reasoning_mode_raises(self, tmp_path: Path) -> None:
        """An unrecognized reasoning mode must be rejected by Pydantic."""
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(
            textwrap.dedent("""\
                version: 1
                reasoning:
                  mode: turbo
            """),
            encoding="utf-8",
        )
        with pytest.raises(ConfigurationError):
            load_config(cfg_path)

    def test_enabled_mode_ollama_provider_valid(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(
            textwrap.dedent("""\
                version: 1
                reasoning:
                  mode: enabled
                  provider:
                    type: ollama
                    model: qwen3
            """),
            encoding="utf-8",
        )
        cfg = load_config(cfg_path)
        assert cfg.reasoning.mode == "enabled"
        assert cfg.reasoning.provider.type == "ollama"
        assert cfg.reasoning.provider.model == "qwen3"

    def test_inspection_max_file_size_must_be_positive(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(
            textwrap.dedent("""\
                version: 1
                inspection:
                  max_file_size_kb: 0
            """),
            encoding="utf-8",
        )
        with pytest.raises(ConfigurationError):
            load_config(cfg_path)

    def test_capability_bindings_valid(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(
            textwrap.dedent("""\
                version: 1
                capability_bindings:
                  "app.py::process_doc": "knowledge.search"
                  "app.py::persist_data": "refund.create"
            """),
            encoding="utf-8",
        )
        cfg = load_config(cfg_path)
        assert cfg.capability_bindings == {
            "app.py::process_doc": "knowledge.search",
            "app.py::persist_data": "refund.create",
        }

    def test_capability_bindings_empty_key_rejected(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(
            textwrap.dedent("""\
                version: 1
                capability_bindings:
                  "  ": "knowledge.search"
            """),
            encoding="utf-8",
        )
        with pytest.raises(ConfigurationError, match="empty"):
            load_config(cfg_path)

    def test_capability_bindings_empty_val_rejected(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.yaml"
        cfg_path.write_text(
            textwrap.dedent("""\
                version: 1
                capability_bindings:
                  "app.py::process_doc": "  "
            """),
            encoding="utf-8",
        )
        with pytest.raises(ConfigurationError, match="empty"):
            load_config(cfg_path)


class TestWriteDefaultConfig:
    def test_creates_file(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "config.yaml"
        write_default_config(cfg_path)
        assert cfg_path.is_file()

    def test_written_file_is_valid_yaml(self, tmp_path: Path) -> None:
        import yaml

        cfg_path = tmp_path / "config.yaml"
        write_default_config(cfg_path)
        parsed = yaml.safe_load(cfg_path.read_text())
        assert parsed["version"] == 1
        assert parsed.get("capability_bindings") == {}

    def test_write_to_missing_dir_raises(self, tmp_path: Path) -> None:
        cfg_path = tmp_path / "nonexistent" / "config.yaml"
        with pytest.raises(ConfigurationError):
            write_default_config(cfg_path)
