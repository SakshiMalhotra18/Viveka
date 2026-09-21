"""Tests for Phase 6 world and mutation vocabulary enums."""

from viveka.worlds.vocabulary import (
    MUTATION_FAMILIES,
    DocumentTrust,
    MutationFamily,
    MutationOperator,
    ToolBehavior,
    WorldSlotKind,
)


def test_world_slot_kind_enum():
    assert WorldSlotKind.USER == "user"
    assert WorldSlotKind.INPUT == "input"
    assert WorldSlotKind.RETRIEVAL == "retrieval"
    assert WorldSlotKind.TOOLS == "tools"
    assert WorldSlotKind.ENVIRONMENT == "environment"
    assert WorldSlotKind.STATE == "state"
    assert WorldSlotKind.AUTHORIZATION == "authorization"
    assert len(WorldSlotKind) == 7


def test_document_trust_enum():
    assert DocumentTrust.TRUSTED == "trusted"
    assert DocumentTrust.UNTRUSTED == "untrusted"
    assert DocumentTrust.MIXED == "mixed"


def test_tool_behavior_enum():
    assert ToolBehavior.NORMAL == "normal"
    assert ToolBehavior.TIMEOUT == "timeout"
    assert ToolBehavior.EXCEPTION == "exception"
    assert ToolBehavior.EMPTY_RESULT == "empty_result"


def test_mutation_family_enum():
    assert len(MutationFamily) == 6
    assert MutationFamily.INPUT == "input"
    assert MutationFamily.RETRIEVAL == "retrieval"
    assert MutationFamily.TOOL_RESULT == "tool_result"
    assert MutationFamily.ENVIRONMENT == "environment"
    assert MutationFamily.STATE == "state"
    assert MutationFamily.AUTHORIZATION == "authorization"


def test_mutation_operator_family_mapping_completeness():
    # Every operator in MutationOperator must be mapped in MUTATION_FAMILIES
    for op in MutationOperator:
        assert op in MUTATION_FAMILIES, f"Operator {op} is missing from MUTATION_FAMILIES"
        assert isinstance(MUTATION_FAMILIES[op], MutationFamily)
