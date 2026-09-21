"""
Controlled vocabularies for VIVEKA Phase 4 capability classification.

These StrEnum types form the semantic vocabulary used to tag capabilities,
classify side-effects, externality, reversibility, and trust roles without
invoking any LLM or executing target code.

All values are deliberately conservative:
  - ``unknown`` is always a valid, preferred alternative to a wrong label.
  - Tags describe *what a symbol appears capable of*; they do NOT assign risk.
"""

from __future__ import annotations

from enum import StrEnum


class CapabilityTag(StrEnum):
    """Semantic tag describing an observed capability of a target symbol.

    Tags describe structural evidence only — no risk scoring, no subjective
    assessment.  Multiple tags may apply to the same symbol.
    """

    # Filesystem
    FILESYSTEM_READ = "filesystem_read"
    FILESYSTEM_WRITE = "filesystem_write"
    FILESYSTEM_DELETE = "filesystem_delete"

    # Network I/O
    NETWORK_READ = "network_read"
    NETWORK_WRITE = "network_write"

    # External system access (generic — use more specific tags when possible)
    EXTERNAL_READ = "external_read"
    EXTERNAL_WRITE = "external_write"

    # Data / secrets
    SENSITIVE_READ = "sensitive_read"
    SECRET_ACCESS = "secret_access"

    # Process / execution
    SHELL_EXECUTION = "shell_execution"
    CODE_EXECUTION = "code_execution"

    # Database
    DATABASE_READ = "database_read"
    DATABASE_WRITE = "database_write"

    # Communication
    COMMUNICATION = "communication"

    # Financial
    FINANCIAL_READ = "financial_read"
    FINANCIAL_WRITE = "financial_write"

    # Data access patterns
    READ = "read"
    WRITE = "write"
    RETRIEVAL = "retrieval"

    # Trust / security
    UNTRUSTED_INPUT = "untrusted_input"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"

    # Mutation intent
    SIDE_EFFECT = "side_effect"
    DESTRUCTIVE_WRITE = "destructive_write"

    # Fallback
    UNKNOWN = "unknown"


class SideEffect(StrEnum):
    """Classification of the mutation side-effect profile of a capability."""

    NONE = "none"
    READ_ONLY = "read_only"
    MUTATING = "mutating"
    DESTRUCTIVE = "destructive"
    UNKNOWN = "unknown"


class Externality(StrEnum):
    """Whether a capability operates locally or touches an external system."""

    LOCAL = "local"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


class Reversibility(StrEnum):
    """Static assessment of whether the capability's effect can be undone."""

    REVERSIBLE = "reversible"
    POSSIBLY_REVERSIBLE = "possibly_reversible"
    IRREVERSIBLE = "irreversible"
    UNKNOWN = "unknown"


class TrustRole(StrEnum):
    """Role this symbol plays in the trust-boundary model.

    Derived purely from static evidence — never from runtime observation.
    """

    TRUSTED_INTERNAL = "trusted_internal"
    """Symbol operates entirely within trusted, internal project boundaries."""

    UNTRUSTED_INGRESS = "untrusted_ingress"
    """Symbol accepts data from an external / untrusted source (e.g. user
    query, web content, tool output)."""

    SENSITIVE_SOURCE = "sensitive_source"
    """Symbol reads sensitive or privileged data (secrets, DB, credentials)."""

    PRIVILEGED_SINK = "privileged_sink"
    """Symbol executes privileged actions (shell, payment, destructive ops)."""

    EXTERNAL_SINK = "external_sink"
    """Symbol sends data to an external destination (email, HTTP POST, etc.)."""

    UNKNOWN = "unknown"
    """Trust role cannot be determined from available static evidence."""
