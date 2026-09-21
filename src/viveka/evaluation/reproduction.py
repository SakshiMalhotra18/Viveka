"""
Reproduction Engine for VIVEKA Phase 8.

Executes N trial runs for a Phase 6 World against a target property using deterministic
SHA-256 seed derivation, enforces property approval and property-world matching
integrity checks, aggregates raw K/N verdict counts, and sets criterion_met.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from viveka.core.ids import new_id
from viveka.evaluation.binding import get_demo_capability_binding
from viveka.evaluation.evaluators import EVALUATOR_REGISTRY
from viveka.evaluation.exceptions import (
    PropertyNotApprovedError,
    PropertyWorldMismatchError,
)
from viveka.evaluation.models import (
    EvaluationContext,
    EvaluationResult,
    ReproductionPolicy,
    ReproductionResult,
    ReproductionRun,
    RuntimeCapabilityBinding,
)
from viveka.evaluation.trace import normalize_trace
from viveka.evaluation.vocabulary import EvaluationVerdict
from viveka.properties.vocabulary import PropertyStatus
from viveka.runtime.factory import create_adapter
from viveka.runtime.mapper import map_world_to_context
from viveka.runtime.models import RuntimeRequest, TargetSpec

if TYPE_CHECKING:
    from viveka.evaluation.store import EvaluationStore
    from viveka.properties.models import Property
    from viveka.worlds.models import World


def derive_run_seed(master_seed: int, seed_namespace: str, run_index: int) -> int:
    """Derive deterministic seed from master_seed + seed_namespace + run_index using SHA-256."""
    seed_str = f"{master_seed}:{seed_namespace}:{run_index}"
    digest = hashlib.sha256(seed_str.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def execute_reproduction(
    property: Property,
    world: World,
    policy: ReproductionPolicy | None = None,
    master_seed: int = 12345,
    seed_namespace: str | None = None,
    binding: RuntimeCapabilityBinding | None = None,
    target_spec: TargetSpec | None = None,
    evaluation_store: EvaluationStore | None = None,
) -> ReproductionResult:
    """Execute N reproduction runs for a World against an approved Property.

    Raises:
        PropertyNotApprovedError: If property status is not APPROVED.
        PropertyWorldMismatchError: If world.property_stable_key != property.stable_key.
    """
    # 1. Integrity check: property status must be APPROVED
    if property.status != PropertyStatus.APPROVED:
        raise PropertyNotApprovedError(
            f"Property '{property.id}' has status '{property.status.value}', but must be 'approved' for verification."
        )

    # 2. Integrity check: world stable key must match property stable key
    if world.property_stable_key != property.stable_key:
        raise PropertyWorldMismatchError(
            f"World '{world.id}' stable key '{world.property_stable_key}' does not match property stable key '{property.stable_key}'."
        )

    effective_policy = policy or ReproductionPolicy(runs=5, minimum_violations=3)
    effective_binding = binding or get_demo_capability_binding()
    effective_target = target_spec or TargetSpec(
        adapter_type="python_callable",
        import_path="viveka.demo.agent:run_demo_agent",
    )
    effective_namespace = seed_namespace or world.id

    adapter = create_adapter(effective_target)

    context = map_world_to_context(world)
    evaluator = EVALUATOR_REGISTRY.get(property.oracle.evaluator_kind)

    runs_detail: list[ReproductionRun] = []
    run_evaluations: list[EvaluationResult] = []

    for i in range(effective_policy.runs):
        run_seed = derive_run_seed(master_seed, effective_namespace, i)
        exec_id = new_id("VRUN")

        req = RuntimeRequest(
            execution_id=exec_id,
            world_id=world.id,
            target=effective_target,
            context=context,
            seed=run_seed,
            timeout_seconds=10.0,
        )

        res = adapter.execute(req)
        trace = normalize_trace(res)

        eval_ctx = EvaluationContext(
            trace=trace,
            property=property,
            world=world,
            binding=effective_binding,
        )

        if evaluator:
            eval_res = evaluator.evaluate(eval_ctx)
        else:
            eval_res = EvaluationResult(
                eval_id=new_id("VEVAL"),
                execution_id=exec_id,
                property_id=property.id,
                property_stable_key=property.stable_key,
                property_revision=property.revision,
                verdict=EvaluationVerdict.INCONCLUSIVE,
                rationale=f"No evaluator registered for evaluator_kind '{property.oracle.evaluator_kind}'.",
            )

        if evaluation_store is not None:
            evaluation_store.save(eval_res)

        run_evaluations.append(eval_res)
        runs_detail.append(
            ReproductionRun(
                run_index=i,
                derived_seed=run_seed,
                execution_id=exec_id,
                trace_id=trace.trace_id,
                evaluation_id=eval_res.eval_id,
                verdict=eval_res.verdict,
            )
        )

    # Derive aggregate counts directly from run records
    v_count = sum(1 for r in runs_detail if r.verdict == EvaluationVerdict.VIOLATION)
    nv_count = sum(1 for r in runs_detail if r.verdict == EvaluationVerdict.NO_OBSERVED_VIOLATION)
    inc_count = sum(1 for r in runs_detail if r.verdict == EvaluationVerdict.INCONCLUSIVE)
    na_count = sum(1 for r in runs_detail if r.verdict == EvaluationVerdict.NOT_APPLICABLE)

    criterion_met = v_count >= effective_policy.minimum_violations
    status_str = "REPRODUCTION CRITERION MET" if criterion_met else "REPRODUCTION CRITERION NOT MET"
    summary = f"{v_count} / {effective_policy.runs} runs violated the property ({status_str})"

    return ReproductionResult(
        property_id=property.id,
        property_stable_key=property.stable_key,
        property_revision=property.revision,
        world_id=world.id,
        master_seed=master_seed,
        seed_namespace=effective_namespace,
        policy=effective_policy,
        runs_detail=runs_detail,
        total_runs=effective_policy.runs,
        violations_count=v_count,
        no_violations_count=nv_count,
        inconclusive_count=inc_count,
        not_applicable_count=na_count,
        criterion_met=criterion_met,
        summary_message=summary,
    )
