"""Unit tests for RegressionStore."""

from pathlib import Path

from viveka.evaluation.models import (
    ReproductionPolicy,
    ReproductionResult,
    ReproductionRun,
)
from viveka.evaluation.vocabulary import EvaluationVerdict
from viveka.properties.models import FlowForbiddenOracle, Property
from viveka.properties.vocabulary import PropertyStatus
from viveka.regression.models import BehavioralRegression, RepresentativeEvidence
from viveka.regression.store import RegressionStore
from viveka.worlds.generate import WorldGenerator


def make_fixture_regression() -> BehavioralRegression:
    prop = Property(
        id="VPROP-01",
        stable_key="flow:test",
        name="test-prop",
        description="test",
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
    policy = ReproductionPolicy(runs=5, minimum_violations=3)

    repro = ReproductionResult(
        property_id=prop.id,
        property_stable_key=prop.stable_key,
        property_revision=prop.revision,
        world_id=world.id,
        master_seed=12345,
        seed_namespace="test-ns",
        policy=policy,
        runs_detail=[
            ReproductionRun(
                run_index=0,
                derived_seed=111,
                execution_id="VRUN-1",
                trace_id="VTRC-1",
                evaluation_id="VEVAL-1",
                verdict=EvaluationVerdict.VIOLATION,
            )
        ],
        total_runs=1,
        violations_count=1,
        no_violations_count=0,
        inconclusive_count=0,
        not_applicable_count=0,
        criterion_met=True,
        summary_message="1 / 1 violations",
    )

    return BehavioralRegression(
        regression_id="VREG-01JEXAMPLEREGRESSION0001",
        fingerprint="a" * 64,
        property_snapshot=prop,
        property_stable_key=prop.stable_key,
        property_revision=prop.revision,
        final_world_snapshot=world,
        final_world_fingerprint="b" * 64,
        original_world_id=world.id,
        original_world_fingerprint="c" * 64,
        reduction_id="VRED-01",
        diag_id="VDIAG-01",
        master_seed=12345,
        seed_namespace="test-ns",
        reproduction_policy=policy,
        historical_reproduction=repro,
        representative_evidence=[
            RepresentativeEvidence(
                execution_id="VRUN-1",
                trace_id="VTRC-1",
                evaluation_id="VEVAL-1",
                verdict=EvaluationVerdict.VIOLATION,
                evidence=[],
            )
        ],
        viveka_version="0.1.2",
    )


def test_regression_store_crud(tmp_path: Path) -> None:
    store = RegressionStore(tmp_path)
    regression = make_fixture_regression()

    saved = store.save(regression)
    assert saved.is_file()
    assert saved.name == f"{regression.regression_id}.yaml"

    loaded = store.load(regression.regression_id)
    assert loaded is not None
    assert loaded.regression_id == regression.regression_id
    assert loaded.property_stable_key == "flow:test"
    assert loaded.final_world_snapshot.id == regression.final_world_snapshot.id
    assert len(loaded.representative_evidence) == 1

    by_fp = store.find_by_fingerprint("a" * 64)
    assert by_fp is not None
    assert by_fp.regression_id == regression.regression_id

    assert len(store.load_all()) == 1
    assert store.clear() == 1
    assert store.load_all() == []
