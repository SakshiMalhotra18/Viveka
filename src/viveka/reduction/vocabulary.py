"""
Vocabulary enums for VIVEKA Phase 9 failure reduction engine.

Defines structural reduction operators and factual search stop reasons.
No minimality or QuickCheck-style terms are used.
"""

from __future__ import annotations

from enum import StrEnum


class ReductionOperator(StrEnum):
    """Deterministic structural reduction operators applied to a World."""

    REMOVE_RETRIEVAL_DOCUMENT = "remove_retrieval_document"
    REMOVE_CONVERSATION_TURN = "remove_conversation_turn"
    REMOVE_MEMORY_ENTRY = "remove_memory_entry"
    REMOVE_TOOL_CONFIG = "remove_tool_config"
    REMOVE_USER_PERMISSION = "remove_user_permission"
    REMOVE_ENV_CONFIG = "remove_env_config"


class ReductionStopReason(StrEnum):
    """Factual reason why the reduction engine stopped search."""

    NO_CANDIDATE_PRESERVED_CRITERION = "no_candidate_preserved_criterion"
    NO_MORE_STRUCTURAL_CANDIDATES = "no_more_structural_candidates"
    CANDIDATE_BUDGET_EXHAUSTED = "candidate_budget_exhausted"
    TRIAL_BUDGET_EXHAUSTED = "trial_budget_exhausted"
    BASELINE_CRITERION_NOT_MET = "baseline_criterion_not_met"
