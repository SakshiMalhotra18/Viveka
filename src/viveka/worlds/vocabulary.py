"""
Controlled vocabularies for VIVEKA Phase 6 world and mutation models.

Defines typed enumerations for world slot categories, document trust levels,
tool behaviors, mutation families, and concrete mutation operators per §16-§17
of the master specification.
"""

from __future__ import annotations

from enum import StrEnum


class WorldSlotKind(StrEnum):
    """Top-level slot categories in a World definition (§16)."""

    USER = "user"
    """Identity, role, and permissions of the simulated user."""

    INPUT = "input"
    """User message or conversation input."""

    RETRIEVAL = "retrieval"
    """Documents and search results available to the agent."""

    TOOLS = "tools"
    """Tool behavior overrides and simulated responses."""

    ENVIRONMENT = "environment"
    """Network, clock, configuration, and infrastructure state."""

    STATE = "state"
    """Conversation history and memory."""

    AUTHORIZATION = "authorization"
    """Permissions, approvals, and identity assertions."""


class DocumentTrust(StrEnum):
    """Trust level assigned to a document in a world."""

    TRUSTED = "trusted"
    """Document from a verified, trusted source."""

    UNTRUSTED = "untrusted"
    """Document from an external or unverified source."""

    MIXED = "mixed"
    """Document with both trusted and untrusted content."""


class ToolBehavior(StrEnum):
    """How a tool behaves in a world (§17.3 tool-result mutations)."""

    NORMAL = "normal"
    TIMEOUT = "timeout"
    EXCEPTION = "exception"
    EMPTY_RESULT = "empty_result"
    PARTIAL_SUCCESS = "partial_success"
    WRONG_TYPE = "wrong_type"
    MALFORMED_JSON = "malformed_json"


class MutationFamily(StrEnum):
    """Top-level mutation family from §17."""

    INPUT = "input"
    """§17.1 Input mutations."""

    RETRIEVAL = "retrieval"
    """§17.2 Retrieval mutations."""

    TOOL_RESULT = "tool_result"
    """§17.3 Tool-result mutations."""

    ENVIRONMENT = "environment"
    """§17.4 Environment mutations."""

    STATE = "state"
    """§17.5 State mutations."""

    AUTHORIZATION = "authorization"
    """§17.6 Authorization mutations."""


class MutationOperator(StrEnum):
    """Concrete mutation operators. Each belongs to one MutationFamily (§17)."""

    # §17.1 Input mutations
    PARAPHRASE = "paraphrase"
    AMBIGUOUS_WORDING = "ambiguous_wording"
    CONFLICTING_INSTRUCTIONS = "conflicting_instructions"
    NESTED_INSTRUCTIONS = "nested_instructions"
    DELIMITER_CHANGES = "delimiter_changes"
    JSON_WRAPPED_INSTRUCTIONS = "json_wrapped_instructions"
    ENCODED_TEXT = "encoded_text"
    LONG_CONTEXT = "long_context"
    IRRELEVANT_DISTRACTORS = "irrelevant_distractors"

    # §17.2 Retrieval mutations
    POISONED_DOCUMENT = "poisoned_document"
    CONFLICTING_DOCUMENTS = "conflicting_documents"
    STALE_DOCUMENT = "stale_document"
    DUPLICATED_RESULT = "duplicated_result"
    MISSING_RESULT = "missing_result"
    MALFORMED_METADATA = "malformed_metadata"
    WRONG_SOURCE_RANKING = "wrong_source_ranking"
    INJECTED_INSTRUCTIONS = "injected_instructions"
    DOCUMENT_TRUNCATION = "document_truncation"

    # §17.3 Tool-result mutations
    TOOL_TIMEOUT = "tool_timeout"
    TOOL_EXCEPTION = "tool_exception"
    TOOL_EMPTY_RESULT = "tool_empty_result"
    TOOL_PARTIAL_SUCCESS = "tool_partial_success"
    TOOL_WRONG_TYPE = "tool_wrong_type"
    TOOL_MALFORMED_JSON = "tool_malformed_json"
    TOOL_DUPLICATED_RESPONSE = "tool_duplicated_response"
    TOOL_STALE_RESPONSE = "tool_stale_response"
    TOOL_CONTRADICTORY_RESPONSE = "tool_contradictory_response"
    TOOL_SUCCESS_THEN_DISCONNECT = "tool_success_then_disconnect"

    # §17.4 Environment mutations
    NETWORK_UNAVAILABLE = "network_unavailable"
    HIGH_LATENCY = "high_latency"
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMIT = "rate_limit"
    CLOCK_SHIFT = "clock_shift"
    MISSING_CONFIGURATION = "missing_configuration"
    UNAVAILABLE_DEPENDENCY = "unavailable_dependency"

    # §17.5 State mutations
    INCOMPLETE_CONVERSATION = "incomplete_conversation"
    STALE_MEMORY = "stale_memory"
    CONFLICTING_MEMORY = "conflicting_memory"
    PRIOR_FAILED_ACTION = "prior_failed_action"
    REPEATED_ACTION = "repeated_action"
    DUPLICATED_STATE_EVENT = "duplicated_state_event"

    # §17.6 Authorization mutations
    USER_LACKS_PERMISSION = "user_lacks_permission"
    APPROVAL_MISSING = "approval_missing"
    APPROVAL_REVOKED = "approval_revoked"
    ACTION_EXCEEDS_THRESHOLD = "action_exceeds_threshold"
    IDENTITY_MISMATCH = "identity_mismatch"


# ---------------------------------------------------------------------------
# Mutation family mapping
# ---------------------------------------------------------------------------

MUTATION_FAMILIES: dict[MutationOperator, MutationFamily] = {
    # §17.1 Input
    MutationOperator.PARAPHRASE: MutationFamily.INPUT,
    MutationOperator.AMBIGUOUS_WORDING: MutationFamily.INPUT,
    MutationOperator.CONFLICTING_INSTRUCTIONS: MutationFamily.INPUT,
    MutationOperator.NESTED_INSTRUCTIONS: MutationFamily.INPUT,
    MutationOperator.DELIMITER_CHANGES: MutationFamily.INPUT,
    MutationOperator.JSON_WRAPPED_INSTRUCTIONS: MutationFamily.INPUT,
    MutationOperator.ENCODED_TEXT: MutationFamily.INPUT,
    MutationOperator.LONG_CONTEXT: MutationFamily.INPUT,
    MutationOperator.IRRELEVANT_DISTRACTORS: MutationFamily.INPUT,
    # §17.2 Retrieval
    MutationOperator.POISONED_DOCUMENT: MutationFamily.RETRIEVAL,
    MutationOperator.CONFLICTING_DOCUMENTS: MutationFamily.RETRIEVAL,
    MutationOperator.STALE_DOCUMENT: MutationFamily.RETRIEVAL,
    MutationOperator.DUPLICATED_RESULT: MutationFamily.RETRIEVAL,
    MutationOperator.MISSING_RESULT: MutationFamily.RETRIEVAL,
    MutationOperator.MALFORMED_METADATA: MutationFamily.RETRIEVAL,
    MutationOperator.WRONG_SOURCE_RANKING: MutationFamily.RETRIEVAL,
    MutationOperator.INJECTED_INSTRUCTIONS: MutationFamily.RETRIEVAL,
    MutationOperator.DOCUMENT_TRUNCATION: MutationFamily.RETRIEVAL,
    # §17.3 Tool-result
    MutationOperator.TOOL_TIMEOUT: MutationFamily.TOOL_RESULT,
    MutationOperator.TOOL_EXCEPTION: MutationFamily.TOOL_RESULT,
    MutationOperator.TOOL_EMPTY_RESULT: MutationFamily.TOOL_RESULT,
    MutationOperator.TOOL_PARTIAL_SUCCESS: MutationFamily.TOOL_RESULT,
    MutationOperator.TOOL_WRONG_TYPE: MutationFamily.TOOL_RESULT,
    MutationOperator.TOOL_MALFORMED_JSON: MutationFamily.TOOL_RESULT,
    MutationOperator.TOOL_DUPLICATED_RESPONSE: MutationFamily.TOOL_RESULT,
    MutationOperator.TOOL_STALE_RESPONSE: MutationFamily.TOOL_RESULT,
    MutationOperator.TOOL_CONTRADICTORY_RESPONSE: MutationFamily.TOOL_RESULT,
    MutationOperator.TOOL_SUCCESS_THEN_DISCONNECT: MutationFamily.TOOL_RESULT,
    # §17.4 Environment
    MutationOperator.NETWORK_UNAVAILABLE: MutationFamily.ENVIRONMENT,
    MutationOperator.HIGH_LATENCY: MutationFamily.ENVIRONMENT,
    MutationOperator.PERMISSION_DENIED: MutationFamily.ENVIRONMENT,
    MutationOperator.RATE_LIMIT: MutationFamily.ENVIRONMENT,
    MutationOperator.CLOCK_SHIFT: MutationFamily.ENVIRONMENT,
    MutationOperator.MISSING_CONFIGURATION: MutationFamily.ENVIRONMENT,
    MutationOperator.UNAVAILABLE_DEPENDENCY: MutationFamily.ENVIRONMENT,
    # §17.5 State
    MutationOperator.INCOMPLETE_CONVERSATION: MutationFamily.STATE,
    MutationOperator.STALE_MEMORY: MutationFamily.STATE,
    MutationOperator.CONFLICTING_MEMORY: MutationFamily.STATE,
    MutationOperator.PRIOR_FAILED_ACTION: MutationFamily.STATE,
    MutationOperator.REPEATED_ACTION: MutationFamily.STATE,
    MutationOperator.DUPLICATED_STATE_EVENT: MutationFamily.STATE,
    # §17.6 Authorization
    MutationOperator.USER_LACKS_PERMISSION: MutationFamily.AUTHORIZATION,
    MutationOperator.APPROVAL_MISSING: MutationFamily.AUTHORIZATION,
    MutationOperator.APPROVAL_REVOKED: MutationFamily.AUTHORIZATION,
    MutationOperator.ACTION_EXCEEDS_THRESHOLD: MutationFamily.AUTHORIZATION,
    MutationOperator.IDENTITY_MISMATCH: MutationFamily.AUTHORIZATION,
}
