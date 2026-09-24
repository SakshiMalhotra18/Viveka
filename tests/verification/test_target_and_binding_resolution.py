"""Focused unit tests for VerificationEngine and ReplayEngine target & binding resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from viveka.core.config import VivekaConfig
from viveka.core.errors import ConfigurationError
from viveka.evaluation.models import RuntimeCapabilityBinding
from viveka.regression.replay import ReplayEngine
from viveka.runtime.vocabulary import RuntimeAdapterType
from viveka.verification.engine import VerificationEngine


class TestVerificationEngineTargetAndBindingResolution:
    def test_http_target_and_bindings_from_config(self, tmp_path: Path) -> None:
        """VerificationEngine resolves HTTP target and capability_bindings from config."""
        config = VivekaConfig(version=1)
        config.runtime.adapter = "http"
        config.interface.endpoint = "http://localhost:8080/agent"
        config.capability_bindings = {
            "app.py::process_doc": "knowledge.search",
            "app.py::persist_data": "refund.create",
        }

        engine = VerificationEngine(project_root=tmp_path, config=config)
        target, binding = engine.resolve_target_and_binding()

        assert target.adapter_type == RuntimeAdapterType.HTTP
        assert target.endpoint == "http://localhost:8080/agent"
        assert binding.bindings == {
            "app.py::process_doc": "knowledge.search",
            "app.py::persist_data": "refund.create",
        }

    def test_explicit_binding_overrides_config(self, tmp_path: Path) -> None:
        """Explicit RuntimeCapabilityBinding takes precedence over config capability_bindings."""
        config = VivekaConfig(version=1)
        config.runtime.adapter = "http"
        config.interface.endpoint = "http://localhost:8080/agent"
        config.capability_bindings = {"config_key": "config_tool"}

        explicit = RuntimeCapabilityBinding(bindings={"explicit_key": "explicit_tool"})
        engine = VerificationEngine(project_root=tmp_path, config=config)
        _target, binding = engine.resolve_target_and_binding(explicit_binding=explicit)

        assert binding.bindings == {"explicit_key": "explicit_tool"}

    def test_demo_agent_binding_resolution(self, tmp_path: Path) -> None:
        """Demo agent without explicit or configured binding gets demo binding."""
        config = VivekaConfig(version=1)
        config.runtime.adapter = "python"
        config.runtime.command = "viveka.demo.agent:run_demo_agent"

        engine = VerificationEngine(project_root=tmp_path, config=config)
        target, binding = engine.resolve_target_and_binding()

        assert target.import_path == "viveka.demo.agent:run_demo_agent"
        assert "src/read.py::search" in binding.bindings

    def test_non_demo_python_target_without_binding_raises(self, tmp_path: Path) -> None:
        """Non-demo Python target without configured or explicit binding raises ConfigurationError."""
        config = VivekaConfig(version=1)
        config.runtime.adapter = "python"
        config.runtime.command = "my_custom_agent:run"

        engine = VerificationEngine(project_root=tmp_path, config=config)
        with pytest.raises(ConfigurationError, match="No capability binding configured"):
            engine.resolve_target_and_binding()

    def test_custom_http_target_without_binding_raises(self, tmp_path: Path) -> None:
        """Custom HTTP target without configured or explicit binding raises ConfigurationError."""
        config = VivekaConfig(version=1)
        config.runtime.adapter = "http"
        config.interface.endpoint = "http://localhost:8080/agent"
        config.capability_bindings = {}

        engine = VerificationEngine(project_root=tmp_path, config=config)
        with pytest.raises(ConfigurationError, match="No capability binding configured"):
            engine.resolve_target_and_binding()

    def test_custom_mcp_target_without_binding_raises(self, tmp_path: Path) -> None:
        """Custom MCP target without configured or explicit binding raises ConfigurationError."""
        config = VivekaConfig(version=1)
        config.runtime.adapter = "mcp"
        config.mcp.command = "npx"
        config.mcp.args = ["-y", "@modelcontextprotocol/server-memory"]
        config.capability_bindings = {}

        engine = VerificationEngine(project_root=tmp_path, config=config)
        with pytest.raises(ConfigurationError, match="No capability binding configured"):
            engine.resolve_target_and_binding()

    def test_mcp_target_and_bindings_from_config(self, tmp_path: Path) -> None:
        """VerificationEngine resolves MCP target and capability_bindings from config."""
        config = VivekaConfig(version=1)
        config.runtime.adapter = "mcp"
        config.mcp.command = "npx"
        config.mcp.args = ["-y", "@modelcontextprotocol/server-memory"]
        config.capability_bindings = {
            "app.py::remember": "create_entities",
        }

        engine = VerificationEngine(project_root=tmp_path, config=config)
        target, binding = engine.resolve_target_and_binding()

        assert target.adapter_type == RuntimeAdapterType.MCP
        assert binding.bindings == {"app.py::remember": "create_entities"}


class TestReplayEngineTargetAndBindingResolution:
    def test_replay_resolves_http_and_bindings_from_config(self, tmp_path: Path) -> None:
        """ReplayEngine resolves HTTP target and capability_bindings from config."""
        config = VivekaConfig(version=1)
        config.runtime.adapter = "http"
        config.interface.endpoint = "http://localhost:9000/agent"
        config.capability_bindings = {
            "app.py::query": "search.tool",
            "app.py::write": "db.tool",
        }

        engine = ReplayEngine(project_root=tmp_path, config=config)
        target, binding = engine.resolve_target_and_binding()

        assert target.adapter_type == RuntimeAdapterType.HTTP
        assert target.endpoint == "http://localhost:9000/agent"
        assert binding.bindings == {
            "app.py::query": "search.tool",
            "app.py::write": "db.tool",
        }

    def test_replay_explicit_binding_overrides_config(self, tmp_path: Path) -> None:
        """Explicit RuntimeCapabilityBinding takes precedence over config in ReplayEngine."""
        config = VivekaConfig(version=1)
        config.runtime.adapter = "http"
        config.interface.endpoint = "http://localhost:9000/agent"
        config.capability_bindings = {"config_key": "config_tool"}

        explicit = RuntimeCapabilityBinding(bindings={"explicit_key": "explicit_tool"})
        engine = ReplayEngine(project_root=tmp_path, config=config)
        _target, binding = engine.resolve_target_and_binding(explicit_binding=explicit)

        assert binding.bindings == {"explicit_key": "explicit_tool"}

    def test_replay_missing_binding_for_custom_target_raises(self, tmp_path: Path) -> None:
        """ReplayEngine raises ConfigurationError when custom target has no binding."""
        config = VivekaConfig(version=1)
        config.runtime.adapter = "python"
        config.runtime.command = "my_custom_agent:run"

        engine = ReplayEngine(project_root=tmp_path, config=config)
        with pytest.raises(ConfigurationError, match="No capability binding configured"):
            engine.resolve_target_and_binding()

    def test_replay_custom_http_target_without_binding_raises(self, tmp_path: Path) -> None:
        """ReplayEngine raises ConfigurationError when custom HTTP target has no binding."""
        config = VivekaConfig(version=1)
        config.runtime.adapter = "http"
        config.interface.endpoint = "http://localhost:9000/agent"
        config.capability_bindings = {}

        engine = ReplayEngine(project_root=tmp_path, config=config)
        with pytest.raises(ConfigurationError, match="No capability binding configured"):
            engine.resolve_target_and_binding()

    def test_replay_custom_mcp_target_without_binding_raises(self, tmp_path: Path) -> None:
        """ReplayEngine raises ConfigurationError when custom MCP target has no binding."""
        config = VivekaConfig(version=1)
        config.runtime.adapter = "mcp"
        config.mcp.command = "npx"
        config.mcp.args = ["-y", "@modelcontextprotocol/server-memory"]
        config.capability_bindings = {}

        engine = ReplayEngine(project_root=tmp_path, config=config)
        with pytest.raises(ConfigurationError, match="No capability binding configured"):
            engine.resolve_target_and_binding()
