"""
Behavioral Regression Replay Engine for VIVEKA Phase 10.

Replays a stored BehavioralRegression against the target using the stored
stochastic schedule (master_seed, seed_namespace, ReproductionPolicy).

Semantics:
  - Validates internal consistency of BehavioralRegression before replay.
  - Resolves target and capability binding from project config; never silently defaults to demo agent.
  - Strictly uses stored Property snapshot semantics for execution.
  - Detects and explicitly reports Property revision mismatches.
  - Produces factual ReplayReport with raw K/N counts.
  - Never uses FIXED, REGRESSED, safer, or statistical significance terms.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from viveka.core.errors import ConfigurationError
from viveka.evaluation.binding import get_demo_capability_binding
from viveka.evaluation.models import RuntimeCapabilityBinding
from viveka.reduction.runner import DefaultReproductionRunner, ReproductionRunnerProtocol
from viveka.regression.fingerprint import compute_regression_fingerprint
from viveka.regression.models import BehavioralRegression, ReplayReport
from viveka.runtime.models import TargetSpec
from viveka.runtime.vocabulary import RuntimeAdapterType

if TYPE_CHECKING:
    from pathlib import Path

    from viveka.core.config import VivekaConfig
    from viveka.properties.store import PropertyStore


class ReplayEngine:
    """Replays stored BehavioralRegression artifacts against a target."""

    def __init__(
        self,
        project_root: Path,
        runner: ReproductionRunnerProtocol | None = None,
        property_store: PropertyStore | None = None,
        config: VivekaConfig | None = None,
    ) -> None:
        self.project_root = project_root.resolve()
        self.runner = runner or DefaultReproductionRunner()
        self.property_store = property_store
        self.config = config

    def validate_regression_integrity(self, regression: BehavioralRegression) -> None:
        """Validate internal consistency of the BehavioralRegression artifact.

        Raises:
            ValueError: If any internal consistency check fails.
        """
        if regression.property_snapshot.stable_key != regression.property_stable_key:
            raise ValueError(
                f"Regression artifact integrity error: property_snapshot.stable_key "
                f"('{regression.property_snapshot.stable_key}') does not match "
                f"regression.property_stable_key ('{regression.property_stable_key}')."
            )
        if regression.property_snapshot.revision != regression.property_revision:
            raise ValueError(
                f"Regression artifact integrity error: property_snapshot.revision "
                f"({regression.property_snapshot.revision}) does not match "
                f"regression.property_revision ({regression.property_revision})."
            )

        recomputed_fp = compute_regression_fingerprint(
            property_stable_key=regression.property_stable_key,
            property_revision=regression.property_revision,
            final_world=regression.final_world_snapshot,
            policy=regression.reproduction_policy,
            master_seed=regression.master_seed,
            seed_namespace=regression.seed_namespace,
        )
        if recomputed_fp != regression.fingerprint:
            raise ValueError(
                f"Regression artifact integrity error: recomputed fingerprint "
                f"('{recomputed_fp}') does not match stored fingerprint ('{regression.fingerprint}')."
            )

    def resolve_target_and_binding(
        self,
        explicit_target: TargetSpec | None = None,
        explicit_binding: RuntimeCapabilityBinding | None = None,
    ) -> tuple[TargetSpec, RuntimeCapabilityBinding]:
        """Resolve target and capability binding from explicit args or project config.

        Never silently falls back to the demo agent.
        """
        target = explicit_target
        binding = explicit_binding

        if target is None:
            if self.config is not None and self.config.runtime.command:
                target = TargetSpec(
                    adapter_type=RuntimeAdapterType.PYTHON_CALLABLE,
                    import_path=self.config.runtime.command,
                    working_directory=self.config.runtime.working_directory,
                )
            else:
                raise ConfigurationError(
                    "No runtime target configured in .viveka/config.yaml (runtime.command is empty). "
                    "Replay requires an explicit target agent configuration.",
                    hint="Set runtime.command in .viveka/config.yaml or pass target_spec explicitly.",
                )

        if binding is None:
            if target.import_path == "viveka.demo.agent:run_demo_agent":
                binding = get_demo_capability_binding()
            else:
                raise ConfigurationError(
                    f"No capability binding configured for target '{target.import_path}'.",
                    hint="Define a RuntimeCapabilityBinding for the target tools.",
                )

        return target, binding

    def replay(
        self,
        regression: BehavioralRegression,
        target_spec: TargetSpec | None = None,
        binding: RuntimeCapabilityBinding | None = None,
    ) -> ReplayReport:
        """Execute reproduction replay of a stored BehavioralRegression.

        Replay uses stored master_seed, seed_namespace, reproduction_policy,
        and final_world_snapshot.

        Args:
            regression: BehavioralRegression artifact.
            target_spec: Optional explicit TargetSpec. If None, resolved from project config.
            binding: Optional explicit RuntimeCapabilityBinding. If None, resolved from config.

        Returns:
            ReplayReport with factual K/N comparison.
        """
        # 1. Validate artifact integrity
        self.validate_regression_integrity(regression)

        # 2. Check for Property revision mismatch against project PropertyStore
        property_version_mismatch = False
        property_mismatch_detail = ""
        if self.property_store is not None:
            current_prop = self.property_store.get(regression.property_snapshot.id)
            if current_prop is None:
                current_prop = self.property_store.load_catalog().by_stable_key(
                    regression.property_stable_key
                )
            if current_prop is not None and current_prop.revision != regression.property_revision:
                property_version_mismatch = True
                property_mismatch_detail = (
                    f"Stored regression uses property revision {regression.property_revision}, "
                    f"but project current revision is {current_prop.revision}. "
                    "Stored property semantics were used for replay."
                )

        # 3. Resolve target and capability binding
        eff_target, eff_binding = self.resolve_target_and_binding(
            explicit_target=target_spec, explicit_binding=binding
        )

        # 4. Execute reproduction using stored parameters
        current_repro = self.runner.execute_reproduction(
            property=regression.property_snapshot,
            world=regression.final_world_snapshot,
            policy=regression.reproduction_policy,
            master_seed=regression.master_seed,
            seed_namespace=regression.seed_namespace,
            binding=eff_binding,
            target_spec=eff_target,
        )

        hist_repro = regression.historical_reproduction

        # 5. Build factual observations (no FIXED / REGRESSED claims)
        observations: list[str] = []
        if current_repro.violations_count < hist_repro.violations_count:
            observations.append("The saved World reproduced less frequently in this replay.")
        elif current_repro.violations_count > hist_repro.violations_count:
            observations.append("The saved World reproduced more frequently in this replay.")
        else:
            observations.append("The violation count was the same as the historical record.")

        if current_repro.criterion_met:
            observations.append("The configured reproduction criterion was met.")
        else:
            observations.append("The configured reproduction criterion was not met.")

        if property_version_mismatch:
            observations.append(property_mismatch_detail)

        return ReplayReport(
            regression_id=regression.regression_id,
            property_stable_key=regression.property_stable_key,
            property_revision=regression.property_revision,
            historical_violations=hist_repro.violations_count,
            historical_no_observed_violations=hist_repro.no_violations_count,
            historical_inconclusive=hist_repro.inconclusive_count,
            historical_not_applicable=hist_repro.not_applicable_count,
            historical_runs=hist_repro.total_runs,
            historical_criterion_met=hist_repro.criterion_met,
            current_violations=current_repro.violations_count,
            current_no_observed_violations=current_repro.no_violations_count,
            current_inconclusive=current_repro.inconclusive_count,
            current_not_applicable=current_repro.not_applicable_count,
            current_runs=current_repro.total_runs,
            current_criterion_met=current_repro.criterion_met,
            property_version_mismatch=property_version_mismatch,
            property_mismatch_detail=property_mismatch_detail,
            observations=observations,
        )
