"""Tests for Phase 6 deterministic mutation operators."""

import random

import pytest

from viveka.core.ids import new_id
from viveka.worlds.models import World
from viveka.worlds.mutations import (
    MUTATION_REGISTRY,
    deterministic_operators,
)
from viveka.worlds.vocabulary import MutationOperator, ToolBehavior


@pytest.fixture
def base_world() -> World:
    return World(
        id=new_id("VWORLD"),
        property_id="VPROP-0001",
        property_stable_key="test-key",
        seed=123,
    )


def test_deterministic_operators_count():
    ops = deterministic_operators()
    assert len(ops) >= 15
    for op in ops:
        assert op.requires_llm is False


def test_poisoned_document_operator(base_world: World):
    rng = random.Random(42)
    mdef = MUTATION_REGISTRY[MutationOperator.POISONED_DOCUMENT]
    mutated = mdef.apply(base_world, rng)

    assert len(mutated.retrieval.documents) == 1
    assert mutated.retrieval.documents[0].trust == "untrusted"
    assert len(mutated.mutations) == 1
    assert mutated.mutations[0].operator == MutationOperator.POISONED_DOCUMENT


def test_injected_instructions_operator(base_world: World):
    rng = random.Random(42)
    mdef = MUTATION_REGISTRY[MutationOperator.INJECTED_INSTRUCTIONS]
    mutated = mdef.apply(base_world, rng)

    assert len(mutated.retrieval.documents) >= 1
    assert len(mutated.mutations) == 1


def test_nested_instructions_operator(base_world: World):
    rng = random.Random(42)
    mdef = MUTATION_REGISTRY[MutationOperator.NESTED_INSTRUCTIONS]
    mutated = mdef.apply(base_world, rng)

    assert len(mutated.input.message) > 0
    assert len(mutated.mutations) == 1


def test_json_wrapped_instructions_operator(base_world: World):
    rng = random.Random(42)
    mdef = MUTATION_REGISTRY[MutationOperator.JSON_WRAPPED_INSTRUCTIONS]
    mutated = mdef.apply(base_world, rng)

    assert "{" in mutated.input.message
    assert len(mutated.mutations) == 1


def test_tool_timeout_operator(base_world: World):
    rng = random.Random(42)
    mdef = MUTATION_REGISTRY[MutationOperator.TOOL_TIMEOUT]
    mutated = mdef.apply(base_world, rng)

    assert len(mutated.tools) == 1
    tool_cfg = next(iter(mutated.tools.values()))
    assert tool_cfg.behavior == ToolBehavior.TIMEOUT
    assert len(mutated.mutations) == 1


def test_network_unavailable_operator(base_world: World):
    rng = random.Random(42)
    mdef = MUTATION_REGISTRY[MutationOperator.NETWORK_UNAVAILABLE]
    mutated = mdef.apply(base_world, rng)

    assert mutated.environment.network_available is False
    assert len(mutated.mutations) == 1


def test_llm_stub_raises_not_implemented(base_world: World):
    rng = random.Random(42)
    mdef = MUTATION_REGISTRY[MutationOperator.PARAPHRASE]
    assert mdef.requires_llm is True

    with pytest.raises(NotImplementedError, match="requires LLM reasoning"):
        mdef.apply(base_world, rng)
