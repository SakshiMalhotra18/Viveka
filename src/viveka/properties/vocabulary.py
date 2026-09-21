"""
Controlled vocabularies for VIVEKA Phase 5 property models.

Properties define behavioral invariants that an AI agent should uphold.
These StrEnums categorize property lifecycle status, origin sources,
invariant types, and evidence categories.
"""

from __future__ import annotations

from enum import StrEnum


class PropertyStatus(StrEnum):
    """Lifecycle status of a property.

    In VIVEKA, candidate properties are never active verification invariants
    until explicitly approved by a human developer.
    """

    CANDIDATE = "candidate"
    """Proposed by rules or reasoning engines; awaiting human review."""

    APPROVED = "approved"
    """Explicitly approved by the developer; active invariant for verification."""

    REJECTED = "rejected"
    """Explicitly rejected by the developer; will not be verified or re-proposed."""

    DISABLED = "disabled"
    """Temporarily deactivated without being discarded."""

    DEPRECATED = "deprecated"
    """Superseded by a newer property or no longer applicable."""


class PropertySource(StrEnum):
    """Origin tracking for where a property was derived."""

    RULE_DERIVED = "rule-derived"
    """Deterministically inferred from capabilities and trust boundaries."""

    CODE_DERIVED = "code-derived"
    """Extracted from code comments, docstrings, or type annotations."""

    USER_AUTHORED = "user-authored"
    """Directly authored by a human developer."""

    REGRESSION_DERIVED = "regression-derived"
    """Synthesized from a past discovered counterexample failure."""

    MODEL_ASSISTED = "model-assisted"
    """Suggested by an advisory reasoning provider; requires human review."""


class InvariantType(StrEnum):
    """The formal kind of invariant being checked."""

    FORBIDDEN_FLOW = "forbidden_flow"
    """Ingress source A must not flow into or authorize privileged sink B."""

    MUST_HANDLE_FAILURE = "must_handle_failure"
    """If an exposed tool call fails, the agent must not claim the action succeeded."""


class PropertyEvidenceType(StrEnum):
    """Category of supporting evidence bound to a property."""

    CAPABILITY = "capability"
    """Supported by a Phase 4 Capability detection."""

    TRUST_BOUNDARY = "trust_boundary"
    """Supported by a detected trust boundary link."""

    GRAPH_PATH = "graph_path"
    """Supported by a directed path in the static capability graph."""

    STATIC_CALL = "static_call"
    """Supported by a direct static call relationship."""
