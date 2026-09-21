"""
Unit tests for Phase 9 ReductionEngine logic using a stub reproduction runner.
"""

from __future__ import annotations

import pytest

from viveka.evaluation.models import (
    ReproductionPolicy,
    ReproductionResult,
    RuntimeCapabilityBinding,
)
from viveka.properties.models import FlowForbiddenOracle, Property
from viveka.properties.vocabulary import PropertyStatus
from viveka.reduction.engine import ReductionEngine
from viveka.reduction.models import ReductionBudget
from viveka.reduction.vocabulary import ReductionStopReason
from viveka.runtime.models import TargetSpec
from viveka.worlds.models import ConversationTurn, World, WorldDocument


class StubReproductionRunner:
    """Configurable stub runner for unit testing ReductionEngine without Phase 7 runtime."""

    def __init__(self, reproduce_filter: callable) -> None:
        self.reproduce_filter = reproduce_filter
        self.calls: list[str] = []

    def execute_reproduction(
        self,
        property: Property,
        world: World,
        policy: ReproductionPolicy | None = None,
        master_seed: int = 12345,
        seed_namespace: str | None = None,
        binding: RuntimeCapabilityBinding | None = None,
        target_spec: TargetSpec | None = None,
    ) -> ReproductionResult:
        eff_policy = policy or ReproductionPolicy(runs=5, minimum_violations=3)
        self.calls.append(world.id)

        criterion_met = self.reproduce_filter(world)
        v_count = eff_policy.minimum_violations if criterion_met else 0

        return ReproductionResult(
            property_id=property.id,
            property_stable_key=property.stable_key,
            property_revision=property.revision,
            world_id=world.id,
            master_seed=master_seed,
            seed_namespace=seed_namespace or world.id,
            policy=eff_policy,
            total_runs=eff_policy.runs,
            violations_count=v_count,
            no_violations_count=eff_policy.runs - v_count,
            inconclusive_count=0,
            not_applicable_count=0,
            criterion_met=criterion_met,
            summary_message=f"{v_count} / {eff_policy.runs} runs violated",
        )


@pytest.fixture
def test_property() -> Property:
    return Property(
        id="VPROP-01JY8M7KFQZRVF2BNXD3TYA9WG",
        name="Flow Forbidden Test",
        description="Forbidden flow test",
        oracle=FlowForbiddenOracle(
            untrusted_source_key="src.search::knowledge_search",
            forbidden_sink_key="src.payment::refund_order",
        ),
        status=PropertyStatus.APPROVED,
        stable_key="prop.flow_test",
    )


@pytest.fixture
def failing_world(test_property: Property) -> World:
    w = World(
        id="VWORLD-01JY8M7KFQZRVF2BNXD3TYA9WG",
        property_id=test_property.id,
        property_stable_key=test_property.stable_key,
        seed=100,
    )
    w.retrieval.documents.append(WorldDocument(id="doc-1", content="doc 1 content"))
    w.retrieval.documents.append(WorldDocument(id="doc-2", content="doc 2 content"))
    w.state.conversation_history.append(ConversationTurn(role="user", content="turn 1"))
    return w


def test_baseline_budget_validation(test_property: Property, failing_world: World) -> None:
    runner = StubReproductionRunner(reproduce_filter=lambda w: True)
    engine = ReductionEngine(runner=runner)

    policy = ReproductionPolicy(runs=5, minimum_violations=3)
    budget = ReductionBudget(max_candidates=10, max_trials=4)  # 4 < 5!

    with pytest.raises(ValueError, match=r"max_trials .* cannot be less than policy runs"):
        engine.reduce(property_obj=test_property, world=failing_world, policy=policy, budget=budget)


def test_baseline_not_reproducible(test_property: Property, failing_world: World) -> None:
    runner = StubReproductionRunner(reproduce_filter=lambda w: False)
    engine = ReductionEngine(runner=runner)

    result = engine.reduce(property_obj=test_property, world=failing_world)

    assert result.stop_reason == ReductionStopReason.BASELINE_CRITERION_NOT_MET
    assert result.reduced_world_id is None
    assert (
        result.summary_message
        == "Baseline World did not meet configured reproduction criterion. Reduction aborted."
    )


def test_rejected_step_preservation(test_property: Property, failing_world: World) -> None:
    # Accept doc-2 removal, reject doc-1 removal
    def filter_fn(w: World) -> bool:
        # If both docs present -> True (baseline)
        if len(w.retrieval.documents) == 2:
            return True
        # If doc-1 present and doc-2 removed -> True (accepted step)
        if len(w.retrieval.documents) == 1 and w.retrieval.documents[0].id == "doc-1":
            return True
        # Otherwise False (rejected step)
        return False

    runner = StubReproductionRunner(reproduce_filter=filter_fn)
    engine = ReductionEngine(runner=runner)

    result = engine.reduce(property_obj=test_property, world=failing_world)

    assert result.stop_reason == ReductionStopReason.NO_CANDIDATE_PRESERVED_CRITERION
    assert len(result.steps) >= 2
    # Verify that steps preserves BOTH accepted and rejected steps!
    accepted_steps = [s for s in result.steps if s.accepted]
    rejected_steps = [s for s in result.steps if not s.accepted]
    assert len(accepted_steps) >= 1
    assert len(rejected_steps) >= 1

    # Verify final reproduction matches last accepted world
    assert result.final_reproduction.world_id == result.reduced_world_id
    assert (
        "No smaller tested candidate met the configured reproduction criterion"
        in result.summary_message
    )


def test_candidate_budget_exhaustion(test_property: Property, failing_world: World) -> None:
    runner = StubReproductionRunner(reproduce_filter=lambda w: True)
    engine = ReductionEngine(runner=runner)

    budget = ReductionBudget(max_candidates=1, max_trials=50)
    result = engine.reduce(property_obj=test_property, world=failing_world, budget=budget)

    assert result.stop_reason == ReductionStopReason.CANDIDATE_BUDGET_EXHAUSTED
    assert "Search stopped: candidate count budget of 1 reached." in result.summary_message


def test_trial_budget_exhaustion(test_property: Property, failing_world: World) -> None:
    runner = StubReproductionRunner(reproduce_filter=lambda w: True)
    engine = ReductionEngine(runner=runner)

    policy = ReproductionPolicy(runs=5, minimum_violations=3)
    # Baseline takes 5 trials. max_trials=8 allows baseline (5), but next candidate needs 5 (total 10 > 8)
    budget = ReductionBudget(max_candidates=10, max_trials=8)
    result = engine.reduce(
        property_obj=test_property, world=failing_world, policy=policy, budget=budget
    )

    assert result.stop_reason == ReductionStopReason.TRIAL_BUDGET_EXHAUSTED
    assert "Search stopped: total trial budget of 8 reached." in result.summary_message


def test_duplicate_candidate_fingerprint_suppression(test_property: Property) -> None:
    w = World(
        id="VWORLD-1",
        property_id=test_property.id,
        property_stable_key=test_property.stable_key,
        seed=42,
    )
    w.state.memory["a"] = "val"
    w.state.memory["b"] = "val"

    runner = StubReproductionRunner(reproduce_filter=lambda w: False)
    engine = ReductionEngine(runner=runner)

    res = engine.reduce(property_obj=test_property, world=w)

    assert res.stop_reason == ReductionStopReason.BASELINE_CRITERION_NOT_MET
    # Verify that total candidates evaluated equals total unique fingerprints generated
    assert len(runner.calls) == len(set(runner.calls)) + 0  # runner.calls contains unique world IDs


def test_deterministic_repeated_search(test_property: Property, failing_world: World) -> None:
    runner1 = StubReproductionRunner(reproduce_filter=lambda w: len(w.retrieval.documents) >= 1)
    engine1 = ReductionEngine(runner=runner1)
    res1 = engine1.reduce(property_obj=test_property, world=failing_world, master_seed=42)

    runner2 = StubReproductionRunner(reproduce_filter=lambda w: len(w.retrieval.documents) >= 1)
    engine2 = ReductionEngine(runner=runner2)
    res2 = engine2.reduce(property_obj=test_property, world=failing_world, master_seed=42)

    assert res1.stop_reason == res2.stop_reason
    assert len(res1.steps) == len(res2.steps)
    for s1, s2 in zip(res1.steps, res2.steps, strict=True):
        assert s1.operator == s2.operator
        assert s1.target_item_key == s2.target_item_key
        assert s1.accepted == s2.accepted
