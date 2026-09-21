"""CLI tests for Phase 10 commands: diagnose, regression, and replay."""

from pathlib import Path

from typer.testing import CliRunner

from viveka.cli.app import app
from viveka.core.config import write_default_config
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
from viveka.properties.store import PropertyStore
from viveka.properties.vocabulary import PropertyStatus
from viveka.reduction.models import ReductionBudget, ReductionResult
from viveka.reduction.store import ReductionStore
from viveka.reduction.vocabulary import ReductionStopReason
from viveka.runtime.vocabulary import RawEventType
from viveka.worlds.generate import WorldGenerator
from viveka.worlds.store import WorldStore

runner = CliRunner()


def setup_project(tmp_path: Path):
    vd = tmp_path / ".viveka"
    vd.mkdir(parents=True, exist_ok=True)
    write_default_config(vd / "config.yaml")

    prop = Property(
        id="VPROP-01JCLITEST0000000000001",
        stable_key="src/search.py::knowledge_search->src/refund.py::refund_create",
        name="cli-test-prop",
        description="CLI test property",
        status=PropertyStatus.APPROVED,
        revision=1,
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="src/search.py::knowledge_search",
            forbidden_sink_key="src/refund.py::refund_create",
        ),
    )
    prop_store = PropertyStore(tmp_path)
    prop_store.save(prop)

    gen = WorldGenerator(seed=12345)
    world = gen.generate_worlds([prop], max_worlds_per_property=1)[0]
    world_store = WorldStore(tmp_path)
    world_store.save(world)

    eval_store = EvaluationStore(tmp_path)
    eval_res = EvaluationResult(
        eval_id="VEVAL-01JCLITEST000000000001",
        execution_id="VRUN-01",
        property_id=prop.id,
        property_stable_key=prop.stable_key,
        property_revision=prop.revision,
        verdict=EvaluationVerdict.VIOLATION,
        evidence=[
            EvaluationEvidence(
                event_id="VEVT-01",
                sequence=1,
                event_type=RawEventType.TOOL_CALL,
                description="search called",
            )
        ],
        rationale="Violation occurred",
    )
    eval_store.save(eval_res)

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
                evaluation_id=eval_res.eval_id,
                verdict=EvaluationVerdict.VIOLATION,
            ),
            ReproductionRun(
                run_index=1,
                derived_seed=102,
                execution_id="VRUN-02",
                trace_id="VTRC-02",
                evaluation_id=eval_res.eval_id,
                verdict=EvaluationVerdict.VIOLATION,
            ),
            ReproductionRun(
                run_index=2,
                derived_seed=103,
                execution_id="VRUN-03",
                trace_id="VTRC-03",
                evaluation_id=eval_res.eval_id,
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
        reduction_id="VRED-01JCLITEST000000000001",
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
    red_store = ReductionStore(tmp_path)
    red_store.save(reduction)

    return prop, world, reduction


def test_cli_diagnose_command(tmp_path: Path) -> None:
    _prop, _world, reduction = setup_project(tmp_path)

    # 1. Text output
    result = runner.invoke(app, ["diagnose", reduction.reduction_id, "--path", str(tmp_path)])
    assert result.exit_code == 0
    assert "Behavioral Failure Diagnosis" in result.output
    assert reduction.reduction_id in result.output

    # 2. JSON output
    json_result = runner.invoke(
        app, ["diagnose", reduction.reduction_id, "--path", str(tmp_path), "--json"]
    )
    assert json_result.exit_code == 0
    assert '"diag_id"' in json_result.output
    assert '"deterministic_template_v1"' in json_result.output


def test_cli_regression_lifecycle(tmp_path: Path) -> None:
    _prop, _world, reduction = setup_project(tmp_path)

    # 1. Create regression
    res_create = runner.invoke(
        app,
        [
            "regression",
            "create",
            reduction.reduction_id,
            "--path",
            str(tmp_path),
            "--model",
            "demo-agent-v1",
            "--git-commit",
            "abcdef12",
        ],
    )
    assert res_create.exit_code == 0
    assert "Behavioral Regression Created" in res_create.output
    assert "Privacy notice" in res_create.output

    # 2. List regressions
    res_list = runner.invoke(app, ["regression", "list", "--path", str(tmp_path)])
    assert res_list.exit_code == 0
    assert "Stored Behavioral Regressions" in res_list.output
    assert "src/search.py" in res_list.output

    # 3. Show regression (find ID from store)
    from viveka.regression.store import RegressionStore

    reg_store = RegressionStore(tmp_path)
    regs = reg_store.load_all()
    assert len(regs) == 1
    reg_id = regs[0].regression_id

    res_show = runner.invoke(app, ["regression", "show", reg_id, "--path", str(tmp_path)])
    assert res_show.exit_code == 0
    assert "Behavioral Regression Details" in res_show.output
    assert reg_id in res_show.output


def test_cli_replay_command(tmp_path: Path) -> None:
    _prop, _world, reduction = setup_project(tmp_path)

    # Create regression first
    runner.invoke(app, ["regression", "create", reduction.reduction_id, "--path", str(tmp_path)])
    from viveka.regression.store import RegressionStore

    regs = RegressionStore(tmp_path).load_all()
    reg_id = regs[0].regression_id

    # Replay with target override
    res_replay = runner.invoke(
        app,
        [
            "replay",
            reg_id,
            "--path",
            str(tmp_path),
            "--target",
            "viveka.demo.agent:run_demo_agent",
        ],
    )
    assert res_replay.exit_code == 1
    assert "Behavioral Regression Replay Report" in res_replay.output
    assert "Historical" in res_replay.output
    assert "Current" in res_replay.output

    # JSON output
    res_json = runner.invoke(
        app,
        [
            "replay",
            reg_id,
            "--path",
            str(tmp_path),
            "--target",
            "viveka.demo.agent:run_demo_agent",
            "--json",
        ],
    )
    assert res_json.exit_code == 1
    assert '"regression_id"' in res_json.output
    assert '"observations"' in res_json.output
