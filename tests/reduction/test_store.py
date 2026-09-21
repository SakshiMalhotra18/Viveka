"""
Tests for ReductionStore persistence in .viveka/reductions/.
"""

from __future__ import annotations

from pathlib import Path

from viveka.evaluation.models import ReproductionPolicy, ReproductionResult
from viveka.reduction.models import ReductionBudget, ReductionResult
from viveka.reduction.store import ReductionStore
from viveka.reduction.vocabulary import ReductionStopReason


def test_reduction_store_save_load_clear(tmp_path: Path) -> None:
    store = ReductionStore(tmp_path)
    policy = ReproductionPolicy(runs=5, minimum_violations=3)
    budget = ReductionBudget(max_candidates=10, max_trials=50)

    repro = ReproductionResult(
        property_id="VPROP-1",
        property_stable_key="p.key",
        property_revision=1,
        world_id="VWORLD-1",
        master_seed=123,
        seed_namespace="reduction:VWORLD-1",
        policy=policy,
        total_runs=5,
        violations_count=4,
        no_violations_count=1,
        inconclusive_count=0,
        not_applicable_count=0,
        criterion_met=True,
        summary_message="4 / 5 runs violated",
    )

    res = ReductionResult(
        reduction_id="VRED-01JY8M7KFQZRVF2BNXD3TYA9WG",
        property_id="VPROP-1",
        property_stable_key="p.key",
        property_revision=1,
        original_world_id="VWORLD-1",
        stop_reason=ReductionStopReason.NO_MORE_STRUCTURAL_CANDIDATES,
        policy=policy,
        budget=budget,
        master_seed=123,
        seed_namespace="reduction:VWORLD-1",
        baseline_reproduction=repro,
        final_reproduction=repro,
        baseline_trials=5,
        candidate_trials=0,
        total_trials=5,
        summary_message="No smaller tested candidate met the configured reproduction criterion.",
    )

    path = store.save(res)
    assert path.is_file()

    loaded = store.load("VRED-01JY8M7KFQZRVF2BNXD3TYA9WG")
    assert loaded is not None
    assert loaded.reduction_id == res.reduction_id
    assert loaded.stop_reason == ReductionStopReason.NO_MORE_STRUCTURAL_CANDIDATES

    all_res = store.load_all()
    assert len(all_res) == 1

    cleared = store.clear()
    assert cleared == 1
    assert store.load("VRED-01JY8M7KFQZRVF2BNXD3TYA9WG") is None
