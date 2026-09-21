"""Unit tests for ReplayEngine."""

from pathlib import Path

import pytest

from viveka.core.errors import ConfigurationError
from viveka.evaluation.models import (
    ReproductionPolicy,
    ReproductionResult,
    RuntimeCapabilityBinding,
)
from viveka.properties.models import FlowForbiddenOracle, Property
from viveka.properties.store import PropertyStore
from viveka.properties.vocabulary import PropertyStatus
from viveka.reduction.runner import ReproductionRunnerProtocol
from viveka.regression.fingerprint import compute_regression_fingerprint
from viveka.regression.models import BehavioralRegression
from viveka.regression.replay import ReplayEngine
from viveka.runtime.models import TargetSpec
from viveka.worlds.generate import WorldGenerator


class StubRunner(ReproductionRunnerProtocol):
    def __init__(self, violations_count: int, total_runs: int = 5, criterion_met: bool = True):
        self.violations_count = violations_count
        self.total_runs = total_runs
        self.criterion_met = criterion_met

    def execute_reproduction(self, **kwargs) -> ReproductionResult:
        prop = kwargs["property"]
        world = kwargs["world"]
        policy = kwargs.get("policy") or ReproductionPolicy(runs=5, minimum_violations=3)
        return ReproductionResult(
            property_id=prop.id,
            property_stable_key=prop.stable_key,
            property_revision=prop.revision,
            world_id=world.id,
            master_seed=kwargs.get("master_seed", 12345),
            seed_namespace=kwargs.get("seed_namespace", "test"),
            policy=policy,
            runs_detail=[],
            total_runs=self.total_runs,
            violations_count=self.violations_count,
            no_violations_count=self.total_runs - self.violations_count,
            inconclusive_count=0,
            not_applicable_count=0,
            criterion_met=self.criterion_met,
            summary_message=f"{self.violations_count} / {self.total_runs} violations",
        )


def make_valid_regression():
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

    fp = compute_regression_fingerprint(
        prop.stable_key, prop.revision, world, policy, master_seed=12345, seed_namespace="test-ns"
    )

    repro = ReproductionResult(
        property_id=prop.id,
        property_stable_key=prop.stable_key,
        property_revision=prop.revision,
        world_id=world.id,
        master_seed=12345,
        seed_namespace="test-ns",
        policy=policy,
        runs_detail=[],
        total_runs=5,
        violations_count=4,
        no_violations_count=1,
        inconclusive_count=0,
        not_applicable_count=0,
        criterion_met=True,
        summary_message="4 / 5 violations",
    )

    return BehavioralRegression(
        regression_id="VREG-01JTESTREGRESSION000000001",
        fingerprint=fp,
        property_snapshot=prop,
        property_stable_key=prop.stable_key,
        property_revision=prop.revision,
        final_world_snapshot=world,
        final_world_fingerprint="world_fp",
        original_world_id=world.id,
        original_world_fingerprint="world_fp",
        reduction_id="VRED-01",
        diag_id="VDIAG-01",
        master_seed=12345,
        seed_namespace="test-ns",
        reproduction_policy=policy,
        historical_reproduction=repro,
        representative_evidence=[],
        viveka_version="0.1.0",
    )


def test_replay_integrity_failure(tmp_path: Path) -> None:
    reg = make_valid_regression()
    engine = ReplayEngine(project_root=tmp_path)

    # Tamper with fingerprint
    bad_reg = reg.model_copy(update={"fingerprint": "corrupted_fp"})
    with pytest.raises(ValueError, match="integrity error"):
        engine.replay(bad_reg)

    # Tamper with stable_key
    bad_reg2 = reg.model_copy(update={"property_stable_key": "mismatched:key"})
    with pytest.raises(ValueError, match="integrity error"):
        engine.replay(bad_reg2)


def test_replay_target_resolution_failure(tmp_path: Path) -> None:
    reg = make_valid_regression()
    engine = ReplayEngine(project_root=tmp_path)

    # Without config or explicit target, it fails clearly (never silently falls back to demo)
    with pytest.raises(ConfigurationError, match="No runtime target configured"):
        engine.replay(reg)


def test_replay_comparison_observations(tmp_path: Path) -> None:
    reg = make_valid_regression()

    # Case 1: Less frequent violations
    runner1 = StubRunner(violations_count=1, criterion_met=False)
    engine1 = ReplayEngine(project_root=tmp_path, runner=runner1)
    target = TargetSpec(
        adapter_type="python_callable", import_path="viveka.demo.agent:run_demo_agent"
    )
    binding = RuntimeCapabilityBinding(bindings={})

    report1 = engine1.replay(reg, target_spec=target, binding=binding)
    assert report1.historical_violations == 4
    assert report1.current_violations == 1
    assert not report1.current_criterion_met
    assert "less frequently" in " ".join(report1.observations)
    assert "not met" in " ".join(report1.observations).lower()
    # Confirm no forbidden words
    report_text = report1.model_dump_json()
    assert "FIXED" not in report_text
    assert "REGRESSED" not in report_text


def test_replay_property_revision_mismatch_warning(tmp_path: Path) -> None:
    reg = make_valid_regression()
    prop_store = PropertyStore(tmp_path)

    # Save a newer revision (rev 2) in project store
    newer_prop = reg.property_snapshot.model_copy(update={"revision": 2})
    prop_store.save(newer_prop)

    runner = StubRunner(violations_count=4, criterion_met=True)
    engine = ReplayEngine(project_root=tmp_path, runner=runner, property_store=prop_store)
    target = TargetSpec(
        adapter_type="python_callable", import_path="viveka.demo.agent:run_demo_agent"
    )
    binding = RuntimeCapabilityBinding(bindings={})

    report = engine.replay(reg, target_spec=target, binding=binding)
    assert report.property_version_mismatch is True
    assert "revision 1" in report.property_mismatch_detail
    assert "current revision is 2" in report.property_mismatch_detail
