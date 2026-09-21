"""
Behavioral Regression Engine for VIVEKA Phase 10.

Transforms a reproducible failure (from Phase 9 ReductionResult) into a
durable BehavioralRegression artifact.
"""

from __future__ import annotations

import importlib.metadata
from typing import TYPE_CHECKING

from viveka.core.ids import new_id
from viveka.diagnosis.engine import DiagnosisEngine
from viveka.diagnosis.models import TargetMetadata
from viveka.evaluation.vocabulary import EvaluationVerdict
from viveka.properties.vocabulary import PropertyStatus
from viveka.reduction.fingerprint import compute_world_fingerprint
from viveka.regression.fingerprint import compute_regression_fingerprint
from viveka.regression.models import (
    BehavioralRegression,
    RepresentativeEvidence,
)

if TYPE_CHECKING:
    from viveka.diagnosis.models import Diagnosis
    from viveka.diagnosis.store import DiagnosisStore
    from viveka.evaluation.store import EvaluationStore
    from viveka.properties.models import Property
    from viveka.properties.store import PropertyStore
    from viveka.reduction.models import ReductionResult
    from viveka.reduction.store import ReductionStore
    from viveka.regression.store import RegressionStore
    from viveka.worlds.models import World
    from viveka.worlds.store import WorldStore


def get_viveka_version() -> str:
    """Return installed VIVEKA engine version string."""
    try:
        return importlib.metadata.version("viveka-engine")
    except Exception:
        return "0.1.0"


class RegressionEngine:
    """Engine for creating durable BehavioralRegression artifacts."""

    def __init__(
        self,
        property_store: PropertyStore | None = None,
        world_store: WorldStore | None = None,
        reduction_store: ReductionStore | None = None,
        diagnosis_store: DiagnosisStore | None = None,
        regression_store: RegressionStore | None = None,
        evaluation_store: EvaluationStore | None = None,
    ) -> None:
        self.property_store = property_store
        self.world_store = world_store
        self.reduction_store = reduction_store
        self.diagnosis_store = diagnosis_store
        self.regression_store = regression_store
        self.evaluation_store = evaluation_store

    def create(
        self,
        reduction_result: ReductionResult,
        property_obj: Property,
        diagnosis: Diagnosis | None = None,
        target_metadata: TargetMetadata | None = None,
        original_world: World | None = None,
    ) -> BehavioralRegression:
        """Create and persist a BehavioralRegression from a ReductionResult.

        Guards:
          1. Property status must be APPROVED.
          2. Property stable_key and revision must match ReductionResult exactly.
          3. reduction_result.final_reproduction.criterion_met must be True.
          4. There must be at least one VIOLATION run in final_reproduction.

        Returns:
            A saved BehavioralRegression (existing one if fingerprint already exists).
        """
        # Guard 1: Property must be approved
        if property_obj.status != PropertyStatus.APPROVED:
            raise ValueError(
                f"Property '{property_obj.id}' has status '{property_obj.status.value}'. "
                "Only APPROVED properties can be recorded as regressions."
            )

        # Guard 2: Property stable key and revision must match ReductionResult
        if property_obj.stable_key != reduction_result.property_stable_key:
            raise ValueError(
                f"Property stable key mismatch: Property has '{property_obj.stable_key}', "
                f"but ReductionResult recorded '{reduction_result.property_stable_key}'."
            )
        if property_obj.revision != reduction_result.property_revision:
            raise ValueError(
                f"Property revision mismatch: Property has revision {property_obj.revision}, "
                f"but ReductionResult recorded revision {reduction_result.property_revision}."
            )

        # Guard 3: Criterion must be met
        final_repro = reduction_result.final_reproduction
        if not final_repro.criterion_met:
            raise ValueError(
                "ReductionResult did not meet reproduction criterion. "
                "Cannot create a BehavioralRegression from a non-reproducing result."
            )

        # Invariant check: At least one VIOLATION run must exist
        violation_run = next(
            (r for r in final_repro.runs_detail if r.verdict == EvaluationVerdict.VIOLATION),
            None,
        )
        if violation_run is None:
            raise ValueError(
                "Invariant violation: final reproduction criterion_met is True, "
                "but no VIOLATION run was found in runs_detail."
            )

        # Resolve final world snapshot (always present, never None)
        final_world: World | None = reduction_result.reduced_world
        if final_world is None and self.world_store is not None:
            final_world = self.world_store.load(reduction_result.original_world_id)
        if final_world is None and original_world is not None:
            final_world = original_world
        if final_world is None:
            raise ValueError(
                f"Could not resolve final world model for ID '{reduction_result.original_world_id}'."
            )

        # Resolve original world for fingerprint
        orig_world = original_world
        if orig_world is None and self.world_store is not None:
            orig_world = self.world_store.load(reduction_result.original_world_id)
        if orig_world is None:
            orig_world = final_world

        final_world_fp = compute_world_fingerprint(final_world)
        original_world_fp = compute_world_fingerprint(orig_world)

        # Compute regression fingerprint
        fingerprint = compute_regression_fingerprint(
            property_stable_key=property_obj.stable_key,
            property_revision=property_obj.revision,
            final_world=final_world,
            policy=reduction_result.policy,
            master_seed=reduction_result.master_seed,
            seed_namespace=reduction_result.seed_namespace,
        )

        # Deduplication check
        if self.regression_store is not None:
            existing = self.regression_store.find_by_fingerprint(fingerprint)
            if existing is not None:
                return existing

        # Ensure diagnosis exists
        resolved_diag = diagnosis
        if resolved_diag is None:
            diag_engine = DiagnosisEngine()
            resolved_diag = diag_engine.diagnose(
                reduction_result=reduction_result,
                property_obj=property_obj,
                evaluation_store=self.evaluation_store,
            )
            if self.diagnosis_store is not None:
                self.diagnosis_store.save(resolved_diag)

        # Build representative evidence
        rep_evidence: list[RepresentativeEvidence] = []

        # 1. Mandatory VIOLATION representative
        v_eval_evidence = []
        if self.evaluation_store is not None:
            v_eval = self.evaluation_store.load(violation_run.evaluation_id)
            if v_eval is not None:
                v_eval_evidence = v_eval.evidence

        rep_evidence.append(
            RepresentativeEvidence(
                execution_id=violation_run.execution_id,
                trace_id=violation_run.trace_id,
                evaluation_id=violation_run.evaluation_id,
                verdict=EvaluationVerdict.VIOLATION,
                evidence=v_eval_evidence,
            )
        )

        # 2. Optional NO_OBSERVED_VIOLATION representative
        nov_run = next(
            (
                r
                for r in final_repro.runs_detail
                if r.verdict == EvaluationVerdict.NO_OBSERVED_VIOLATION
            ),
            None,
        )
        if nov_run is not None:
            nov_evidence = []
            if self.evaluation_store is not None:
                nov_eval = self.evaluation_store.load(nov_run.evaluation_id)
                if nov_eval is not None:
                    nov_evidence = nov_eval.evidence
            rep_evidence.append(
                RepresentativeEvidence(
                    execution_id=nov_run.execution_id,
                    trace_id=nov_run.trace_id,
                    evaluation_id=nov_run.evaluation_id,
                    verdict=EvaluationVerdict.NO_OBSERVED_VIOLATION,
                    evidence=nov_evidence,
                )
            )

        # 3. Optional INCONCLUSIVE representative
        inc_run = next(
            (r for r in final_repro.runs_detail if r.verdict == EvaluationVerdict.INCONCLUSIVE),
            None,
        )
        if inc_run is not None:
            inc_evidence = []
            if self.evaluation_store is not None:
                inc_eval = self.evaluation_store.load(inc_run.evaluation_id)
                if inc_eval is not None:
                    inc_evidence = inc_eval.evidence
            rep_evidence.append(
                RepresentativeEvidence(
                    execution_id=inc_run.execution_id,
                    trace_id=inc_run.trace_id,
                    evaluation_id=inc_run.evaluation_id,
                    verdict=EvaluationVerdict.INCONCLUSIVE,
                    evidence=inc_evidence,
                )
            )

        regression = BehavioralRegression(
            regression_id=new_id("VREG"),
            fingerprint=fingerprint,
            property_snapshot=property_obj,
            property_stable_key=property_obj.stable_key,
            property_revision=property_obj.revision,
            final_world_snapshot=final_world,
            final_world_fingerprint=final_world_fp,
            original_world_id=reduction_result.original_world_id,
            original_world_fingerprint=original_world_fp,
            reduction_id=reduction_result.reduction_id,
            diag_id=resolved_diag.diag_id if resolved_diag else None,
            diagnosis_snapshot=resolved_diag,
            master_seed=reduction_result.master_seed,
            seed_namespace=reduction_result.seed_namespace,
            reproduction_policy=reduction_result.policy,
            historical_reproduction=final_repro,
            representative_evidence=rep_evidence,
            target_metadata=target_metadata,
            viveka_version=get_viveka_version(),
        )

        if self.regression_store is not None:
            self.regression_store.save(regression)

        return regression
