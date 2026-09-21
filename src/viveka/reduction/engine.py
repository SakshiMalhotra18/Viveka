"""
Reproducible Failure Reduction Engine for VIVEKA Phase 9.

Iteratively simplifies a failing Phase 6 World while preserving the Phase 8
reproduction criterion under shared stochastic seed derivation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from viveka.core.ids import new_id
from viveka.evaluation.models import (
    ReproductionPolicy,
    RuntimeCapabilityBinding,
)
from viveka.reduction.fingerprint import compute_world_fingerprint
from viveka.reduction.models import ReductionBudget, ReductionResult, ReductionStep
from viveka.reduction.operators import generate_reduction_candidates
from viveka.reduction.runner import DefaultReproductionRunner, ReproductionRunnerProtocol
from viveka.reduction.vocabulary import ReductionStopReason
from viveka.runtime.models import TargetSpec
from viveka.worlds.models import World

if TYPE_CHECKING:
    from viveka.evaluation.store import EvaluationStore
    from viveka.properties.models import Property
    from viveka.reduction.store import ReductionStore
    from viveka.worlds.store import WorldStore


class ReductionEngine:
    """Greedy reproducible failure reduction engine."""

    def __init__(
        self,
        runner: ReproductionRunnerProtocol | None = None,
        world_store: WorldStore | None = None,
        reduction_store: ReductionStore | None = None,
        evaluation_store: EvaluationStore | None = None,
    ) -> None:
        self.runner = runner or DefaultReproductionRunner()
        self.world_store = world_store
        self.reduction_store = reduction_store
        self.evaluation_store = evaluation_store

    def reduce(
        self,
        property_obj: Property,
        world: World,
        policy: ReproductionPolicy | None = None,
        budget: ReductionBudget | None = None,
        master_seed: int = 12345,
        binding: RuntimeCapabilityBinding | None = None,
        target_spec: TargetSpec | None = None,
    ) -> ReductionResult:
        """Reduce a failing World to a simpler World that still reproduces the failure.

        Args:
            property_obj: Approved property target.
            world: Original failing World.
            policy: Reproduction policy (runs, minimum_violations).
            budget: Search candidate and trial budget.
            master_seed: Master random seed.
            binding: Target runtime capability binding.
            target_spec: Target agent spec.

        Returns:
            Complete ReductionResult object.

        Raises:
            ValueError: If budget.max_trials < policy.runs.
        """
        effective_policy = policy or ReproductionPolicy(runs=5, minimum_violations=3)
        effective_budget = budget or ReductionBudget(max_candidates=10, max_trials=50)

        # Budget validation before baseline execution
        if effective_budget.max_trials < effective_policy.runs:
            raise ValueError(
                f"max_trials ({effective_budget.max_trials}) cannot be less than policy runs ({effective_policy.runs})."
            )

        shared_namespace = f"reduction:{world.id}"

        # Step 1: Baseline reproduction check
        base_kwargs = {
            "property": property_obj,
            "world": world,
            "policy": effective_policy,
            "master_seed": master_seed,
            "seed_namespace": shared_namespace,
            "binding": binding,
            "target_spec": target_spec,
        }
        if self.evaluation_store is not None:
            base_kwargs["evaluation_store"] = self.evaluation_store
        baseline_repro = self.runner.execute_reproduction(**base_kwargs)

        baseline_trials = effective_policy.runs
        candidate_trials = 0
        total_trials = baseline_trials

        if not baseline_repro.criterion_met:
            result = ReductionResult(
                reduction_id=new_id("VRED"),
                property_id=property_obj.id,
                property_stable_key=property_obj.stable_key,
                property_revision=property_obj.revision,
                original_world_id=world.id,
                reduced_world_id=None,
                reduced_world=None,
                stop_reason=ReductionStopReason.BASELINE_CRITERION_NOT_MET,
                policy=effective_policy,
                budget=effective_budget,
                master_seed=master_seed,
                seed_namespace=shared_namespace,
                baseline_reproduction=baseline_repro,
                final_reproduction=baseline_repro,
                steps=[],
                baseline_trials=baseline_trials,
                candidate_trials=0,
                total_trials=total_trials,
                summary_message="Baseline World did not meet configured reproduction criterion. Reduction aborted.",
            )
            if self.reduction_store:
                self.reduction_store.save(result)
            return result

        # Step 2: Greedy Reduction Loop
        visited_fingerprints: set[str] = {compute_world_fingerprint(world)}
        current_world = world
        current_repro = baseline_repro
        steps: list[ReductionStep] = []
        candidates_count = 0
        stop_reason: ReductionStopReason | None = None

        while True:
            candidates = generate_reduction_candidates(current_world)
            unvisited_candidates = [
                c
                for c in candidates
                if compute_world_fingerprint(c.world) not in visited_fingerprints
            ]

            if not unvisited_candidates:
                if not candidates:
                    stop_reason = ReductionStopReason.NO_MORE_STRUCTURAL_CANDIDATES
                else:
                    stop_reason = ReductionStopReason.NO_CANDIDATE_PRESERVED_CRITERION
                break

            progress_made = False
            for cand in unvisited_candidates:
                cand_fingerprint = compute_world_fingerprint(cand.world)
                visited_fingerprints.add(cand_fingerprint)

                if candidates_count >= effective_budget.max_candidates:
                    stop_reason = ReductionStopReason.CANDIDATE_BUDGET_EXHAUSTED
                    break

                if total_trials + effective_policy.runs > effective_budget.max_trials:
                    stop_reason = ReductionStopReason.TRIAL_BUDGET_EXHAUSTED
                    break

                candidates_count += 1
                candidate_trials += effective_policy.runs
                total_trials += effective_policy.runs

                cand_kwargs = {
                    "property": property_obj,
                    "world": cand.world,
                    "policy": effective_policy,
                    "master_seed": master_seed,
                    "seed_namespace": shared_namespace,
                    "binding": binding,
                    "target_spec": target_spec,
                }
                if self.evaluation_store is not None:
                    cand_kwargs["evaluation_store"] = self.evaluation_store
                cand_repro = self.runner.execute_reproduction(**cand_kwargs)

                accepted = cand_repro.criterion_met
                step = ReductionStep(
                    step_index=len(steps) + 1,
                    candidate_id=cand.candidate_id,
                    parent_world_id=current_world.id,
                    candidate_world_id=cand.world.id,
                    operator=cand.operator,
                    target_item_key=cand.target_item_key,
                    reproduction_result=cand_repro,
                    accepted=accepted,
                )
                steps.append(step)

                if accepted:
                    current_world = cand.world
                    current_repro = cand_repro
                    progress_made = True
                    # Restart outer loop with new simpler world
                    break

            if stop_reason is not None:
                break
            if not progress_made:
                stop_reason = ReductionStopReason.NO_CANDIDATE_PRESERVED_CRITERION
                break

        accepted_count = sum(1 for s in steps if s.accepted)
        if stop_reason in (
            ReductionStopReason.NO_CANDIDATE_PRESERVED_CRITERION,
            ReductionStopReason.NO_MORE_STRUCTURAL_CANDIDATES,
        ):
            summary_message = (
                f"Reduced World {current_world.id} via {accepted_count} accepted step(s). "
                f"No smaller tested candidate met the configured reproduction criterion."
            )
        elif stop_reason == ReductionStopReason.CANDIDATE_BUDGET_EXHAUSTED:
            summary_message = f"Search stopped: candidate count budget of {effective_budget.max_candidates} reached."
        elif stop_reason == ReductionStopReason.TRIAL_BUDGET_EXHAUSTED:
            summary_message = (
                f"Search stopped: total trial budget of {effective_budget.max_trials} reached."
            )
        else:
            summary_message = "Reduction completed."

        final_reduced_world = current_world if accepted_count > 0 else None
        final_reduced_world_id = current_world.id if accepted_count > 0 else None

        result = ReductionResult(
            reduction_id=new_id("VRED"),
            property_id=property_obj.id,
            property_stable_key=property_obj.stable_key,
            property_revision=property_obj.revision,
            original_world_id=world.id,
            reduced_world_id=final_reduced_world_id,
            reduced_world=final_reduced_world,
            stop_reason=stop_reason,
            policy=effective_policy,
            budget=effective_budget,
            master_seed=master_seed,
            seed_namespace=shared_namespace,
            baseline_reproduction=baseline_repro,
            final_reproduction=current_repro,
            steps=steps,
            baseline_trials=baseline_trials,
            candidate_trials=candidate_trials,
            total_trials=total_trials,
            summary_message=summary_message,
        )

        # Persistence: save ONLY the final Reduced Failure World to WorldStore
        if self.world_store and final_reduced_world:
            self.world_store.save(final_reduced_world)

        # Save reduction result record to ReductionStore
        if self.reduction_store:
            self.reduction_store.save(result)

        return result
