"""
VIVEKA configuration model and loader.

Design principles (ADR-0002):
  - This is the SINGLE access point for all VIVEKA settings.
  - No module may call os.getenv() or open config files directly.
  - All settings are injected via the VivekaConfig object.
  - YAML is the user-facing format; Pydantic v2 validates every field.

Config is two-level:
  - Loaded from <project>/.viveka/config.yaml
  - Fields may be overridden by environment variables with VIVEKA_ prefix.

Sections are designed to cover ALL future phases so that early YAML files
remain valid as new features are added. Sections that have no current
implementation are parsed and validated but have no effect yet.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from viveka.core.errors import ConfigurationError

# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class ProjectConfig(BaseModel):
    """Top-level project identity."""

    name: str = "unnamed-project"


class InspectionConfig(BaseModel):
    """Controls how viveka inspect scans the repository."""

    root: str = "."
    honor_gitignore: bool = True
    vivekaignore: str = ".vivekaignore"
    max_file_size_kb: int = Field(default=512, gt=0)
    follow_symlinks: bool = False


ReasoningMode = Literal["none", "enabled"]
ProviderType = Literal["ollama", "openai-compatible"]


class ProviderConfig(BaseModel):
    """Configuration for a reasoning provider."""

    type: ProviderType = "ollama"
    model: str | None = None
    base_url: str | None = None
    # The name of the environment variable that holds the API key.
    # VIVEKA reads the env var — it never stores the key in config.
    api_key_env: str | None = None


class ReasoningConfig(BaseModel):
    """Reasoning provider configuration."""

    mode: ReasoningMode = "none"
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    allow_remote_reasoning: bool = False
    paid_fallback: bool = False
    max_advisory_calls: int = Field(default=20, ge=0)
    request_timeout_seconds: float = Field(default=60.0, gt=0)

    @field_validator("paid_fallback")
    @classmethod
    def warn_on_paid_fallback(cls, v: bool) -> bool:
        if v:
            warnings.warn(
                "reasoning.paid_fallback is set to true. "
                "VIVEKA may incur charges if the configured provider uses a paid model. "
                "Set paid_fallback: false to enforce zero-cost operation.",
                stacklevel=2,
            )
        return v


RuntimeAdapter = Literal["python", "http", "cli", "mcp"]


class RuntimeConfig(BaseModel):
    """How VIVEKA launches and communicates with the target agent."""

    adapter: RuntimeAdapter = "http"
    command: str | None = None
    working_directory: str = "."
    startup_timeout_seconds: int = Field(default=30, gt=0)


class InterfaceConfig(BaseModel):
    """Network interface for the HTTP adapter."""

    endpoint: str | None = None
    healthcheck: str | None = None
    method: str = "POST"
    timeout_seconds: float = Field(default=30.0, gt=0)
    allow_remote_target: bool = False
    auth_header_env: str | None = None
    max_response_bytes: int = Field(default=1048576, gt=0)


McpTransport = Literal["stdio"]


class McpConfig(BaseModel):
    """Configuration for MCP runtime adapter."""

    transport: McpTransport = "stdio"
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    tool: str = "agent.run"
    timeout_seconds: float = Field(default=30.0, gt=0)
    env_from_host: dict[str, str] = Field(default_factory=dict)


class VerificationConfig(BaseModel):
    """Controls the verification pipeline."""

    max_trials_per_property: int = Field(default=50, gt=0)
    seed: int = 12345


class ShrinkingConfig(BaseModel):
    """Controls the counterexample shrinking loop."""

    enabled: bool = True
    max_trials: int = Field(default=50, gt=0)
    timeout_seconds: int = Field(default=120, gt=0)


class PrivacyConfig(BaseModel):
    """Controls what data may leave the local machine."""

    allow_cloud_reasoning: bool = False
    send_source_code: bool = False
    send_trace_content: bool = False
    redact_secrets: bool = True


StorageLocation = Literal["user", "project"]


class StorageConfig(BaseModel):
    """Controls where VIVEKA stores its SQLite database and artifacts."""

    location: StorageLocation = "user"


# ---------------------------------------------------------------------------
# Root config model
# ---------------------------------------------------------------------------


class VivekaConfig(BaseModel):
    """
    Root configuration object for a VIVEKA project.

    Loaded from <project>/.viveka/config.yaml.
    All fields have safe defaults so that viveka init can produce a minimal
    valid config.yaml and every command works from a fresh project.
    """

    version: int = 1

    project: ProjectConfig = Field(default_factory=ProjectConfig)
    inspection: InspectionConfig = Field(default_factory=InspectionConfig)
    reasoning: ReasoningConfig = Field(default_factory=ReasoningConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    interface: InterfaceConfig = Field(default_factory=InterfaceConfig)
    mcp: McpConfig = Field(default_factory=McpConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    shrinking: ShrinkingConfig = Field(default_factory=ShrinkingConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)

    @field_validator("version")
    @classmethod
    def version_must_be_supported(cls, v: int) -> int:
        if v != 1:
            raise ValueError(
                f"Unsupported config version: {v}. "
                "Only version 1 is supported by this release of VIVEKA."
            )
        return v


# ---------------------------------------------------------------------------
# Loader / saver
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG_YAML = """\
version: 1

project:
  name: my-agent

inspection:
  root: .
  honor_gitignore: true
  max_file_size_kb: 512
  follow_symlinks: false

reasoning:
  mode: none
  allow_remote_reasoning: false
  paid_fallback: false

runtime:
  adapter: http
  startup_timeout_seconds: 30

verification:
  max_trials_per_property: 50
  seed: 12345

shrinking:
  enabled: true
  max_trials: 50
  timeout_seconds: 120

privacy:
  allow_cloud_reasoning: false
  send_source_code: false
  send_trace_content: false
  redact_secrets: true

storage:
  location: user
"""


def load_config(path: Path) -> VivekaConfig:
    """Load and validate a VIVEKA config from a YAML file.

    Args:
        path: Absolute path to the config.yaml file.

    Returns:
        A validated :class:`VivekaConfig` instance.

    Raises:
        ConfigurationError: If the file cannot be read or validation fails.
    """
    if not path.is_file():
        raise ConfigurationError(
            f"Configuration file not found: {path}",
            hint="Run `viveka init` to create a project configuration.",
        )
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            f"Could not parse configuration file: {path}\n{exc}",
            hint="Check the YAML syntax in your .viveka/config.yaml.",
        ) from exc
    except OSError as exc:
        raise ConfigurationError(
            f"Could not read configuration file: {path}\n{exc}",
        ) from exc

    try:
        return VivekaConfig.model_validate(raw)
    except Exception as exc:  # pydantic ValidationError
        raise ConfigurationError(
            f"Invalid configuration in {path}:\n{exc}",
            hint="See `viveka config` for documentation on valid settings.",
        ) from exc


def write_default_config(path: Path) -> None:
    """Write a default config.yaml to *path*.

    Args:
        path: Target file path (parent directories must exist).

    Raises:
        ConfigurationError: If the file cannot be written.
    """
    try:
        path.write_text(_DEFAULT_CONFIG_YAML, encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(
            f"Could not write configuration file: {path}\n{exc}",
        ) from exc
