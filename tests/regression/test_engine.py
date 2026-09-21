"""Unit tests for RegressionEngine."""

from pathlib import Path

import pytest

from viveka.evaluation.models import (
    EvaluationEvidence,
    EvaluationResult,
    ReproductionPolicy,
    ReproductionResult,
    ReproductionRun,
)
from viveka.evaluation.store import EvaluationStore
from viveka.evaluation.vocabulary import EvaluationVerdict
from viveka.properties.models import FlowForbiddenOracle, Property
from viveka.properties.vocabulary import PropertyStatus
from viveka.reduction.models import ReductionBudget, ReductionResult
from viveka.reduction.vocabulary import ReductionStopReason
from viveka.regression.engine import RegressionEngine
from viveka.regression.store import RegressionStore
from viveka.runtime.vocabulary import RawEventType
from viveka.worlds.generate import WorldGenerator
from viveka.worlds.store import WorldStore


def make_fixtures(tmp_path: Path):
    prop = Property(
        id="VPROP-01",
        stable_key="src/search.py::knowledge_search->src/refund.py::refund_create",
        name="no-refund",
        description="No refund from search",
        status=PropertyStatus.APPROVED,
        revision=1,
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="src/search.py::knowledge_search",
            forbidden_sink_key="src/refund.py::refund_create",
        ),
    )
    gen = WorldGenerator(seed=12345)
    world = gen.generate_worlds([prop], max_worlds_per_property=1)[0]
    world_store = WorldStore(tmp_path)
    world_store.save(world)

    eval_store = EvaluationStore(tmp_path)
    eval_result = EvaluationResult(
        eval_id="VEVAL-01",
        execution_id="VRUN-01",
        property_id=prop.id,
        property_stable_key=prop.stable_key,
        property_revision=prop.revision,
        verdict=EvaluationVerdict.VIOLATION,
        evidence=[
            EvaluationEvidence(
                event_id="VEVT-1",
                sequence=1,
                event_type=RawEventType.TOOL_CALL,
                description="Evidence 1",
            )
        ],
        rationale="Violation occurred",
    )
    eval_store.save(eval_result)

    policy = ReproductionPolicy(runs=5, minimum_violations=3)
    repro = ReproductionResult(
        property_id=prop.id,
        property_stable_key=prop.stable_key,
        property_revision=prop.revision,
        world_id=world.id,
        master_seed=12345,
        seed_namespace=f"reduction:{world.id}",
        policy=policy,
        runs_detail=[
            ReproductionRun(
                run_index=0,
                derived_seed=101,
                execution_id="VRUN-01",
                trace_id="VTRC-01",
                evaluation_id="VEVAL-01",
                verdict=EvaluationVerdict.VIOLATION,
            ),
            ReproductionRun(
                run_index=1,
                derived_seed=102,
                execution_id="VRUN-02",
                trace_id="VTRC-02",
                evaluation_id="VEVAL-01",
                verdict=EvaluationVerdict.VIOLATION,
            ),
            ReproductionRun(
                run_index=2,
                derived_seed=103,
                execution_id="VRUN-03",
                trace_id="VTRC-03",
                evaluation_id="VEVAL-01",
                verdict=EvaluationVerdict.VIOLATION,
            ),
        ],
        total_runs=3,
        violations_count=3,
        no_violations_count=0,
        inconclusive_count=0,
        not_applicable_count=0,
        criterion_met=True,
        summary_message="3 / 3 violations",
    )

    reduction = ReductionResult(
        reduction_id="VRED-01",
        property_id=prop.id,
        property_stable_key=prop.stable_key,
        property_revision=prop.revision,
        original_world_id=world.id,
        reduced_world_id=world.id,
        reduced_world=world,
        stop_reason=ReductionStopReason.NO_CANDIDATE_PRESERVED_CRITERION,
        policy=policy,
        budget=ReductionBudget(max_candidates=10, max_trials=50),
        master_seed=12345,
        seed_namespace=f"reduction:{world.id}",
        baseline_reproduction=repro,
        final_reproduction=repro,
        steps=[],
        baseline_trials=3,
        candidate_trials=0,
        total_trials=3,
        summary_message="Reduction complete",
    )
    return prop, world, reduction, world_store, eval_store


def test_regression_engine_create_success(tmp_path: Path) -> None:
    prop, world, reduction, world_store, eval_store = make_fixtures(tmp_path)
    reg_store = RegressionStore(tmp_path)

    engine = RegressionEngine(
        world_store=world_store,
        regression_store=reg_store,
        evaluation_store=eval_store,
    )

    regression = engine.create(reduction, prop)
    assert regression.regression_id.startswith("VREG-")
    assert regression.property_stable_key == prop.stable_key
    assert regression.final_world_snapshot is not None
    assert regression.final_world_snapshot.id == world.id
    assert len(regression.representative_evidence) >= 1
    assert regression.representative_evidence[0].verdict == EvaluationVerdict.VIOLATION
    assert len(regression.representative_evidence[0].evidence) == 1
    assert regression.diagnosis_snapshot is not None
    assert regression.master_seed == 12345
    assert regression.seed_namespace == f"reduction:{world.id}"

    # Test deduplication: creating again returns same object
    regression2 = engine.create(reduction, prop)
    assert regression2.regression_id == regression.regression_id


def test_regression_engine_guards(tmp_path: Path) -> None:
    prop, _world, reduction, world_store, eval_store = make_fixtures(tmp_path)
    engine = RegressionEngine(world_store=world_store, evaluation_store=eval_store)

    # 1. Reject candidate property
    cand_prop = prop.model_copy(update={"status": PropertyStatus.CANDIDATE})
    with pytest.raises(ValueError, match="APPROVED"):
        engine.create(reduction, cand_prop)

    # 2. Reject mismatched revision
    rev_prop = prop.model_copy(update={"revision": 2})
    with pytest.raises(ValueError, match="revision mismatch"):
        engine.create(reduction, rev_prop)

    # 3. Reject criterion_met = False
    failed_repro = reduction.final_reproduction.model_copy(update={"criterion_met": False})
    failed_red = reduction.model_copy(update={"final_reproduction": failed_repro})
    with pytest.raises(ValueError, match="reproduction criterion"):
        engine.create(failed_red, prop)
