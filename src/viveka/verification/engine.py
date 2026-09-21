"""
Verification Engine for VIVEKA Phase 11.

Orchestrates inspection, approved property loading, world generation,
runtime execution, reproduction, failure reduction, diagnosis, and regression
persistence into a single verification workflow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from viveka.core.errors import ConfigurationError
from viveka.diagnosis.engine import DiagnosisEngine
from viveka.evaluation.binding import get_demo_capability_binding
from viveka.evaluation.models import (
    ReproductionPolicy,
    RuntimeCapabilityBinding,
)
from viveka.evaluation.reproduction import execute_reproduction
from viveka.properties.vocabulary import PropertyStatus
from viveka.reduction.engine import ReductionEngine
from viveka.reduction.models import ReductionBudget
from viveka.regression.engine import RegressionEngine
from viveka.runtime.models import TargetSpec
from viveka.runtime.vocabulary import RuntimeAdapterType
from viveka.verification.models import (
    PropertyVerificationResult,
    VerificationResult,
    WorldVerificationDetail,
)
from viveka.verification.vocabulary import (
    PropertyVerificationStatus,
    VerificationOutcome,
)
from viveka.worlds.generate import WorldGenerator

if TYPE_CHECKING:
    from pathlib import Path

    from viveka.core.config import VivekaConfig
    from viveka.diagnosis.store import DiagnosisStore
    from viveka.evaluation.store import EvaluationStore
    from viveka.properties.store import PropertyStore
    from viveka.reduction.store import ReductionStore
    from viveka.regression.store import RegressionStore
    from viveka.worlds.store import WorldStore


class VerificationEngine:
    """Orchestrates end-to-end verification of approved properties."""

    def __init__(
        self,
        project_root: Path,
        property_store: PropertyStore | None = None,
        world_store: WorldStore | None = None,
        reduction_store: ReductionStore | None = None,
        diagnosis_store: DiagnosisStore | None = None,
        regression_store: RegressionStore | None = None,
        evaluation_store: EvaluationStore | None = None,
        config: VivekaConfig | None = None,
    ) -> None:
        from viveka.diagnosis.store import DiagnosisStore
        from viveka.evaluation.store import EvaluationStore
        from viveka.properties.store import PropertyStore
        from viveka.reduction.store import ReductionStore
        from viveka.regression.store import RegressionStore
        from viveka.worlds.store import WorldStore

        self.project_root = project_root.resolve()
        self.property_store = property_store or PropertyStore(self.project_root)
        self.world_store = world_store or WorldStore(self.project_root)
        self.reduction_store = reduction_store or ReductionStore(self.project_root)
        self.diagnosis_store = diagnosis_store or DiagnosisStore(self.project_root)
        self.regression_store = regression_store or RegressionStore(self.project_root)
        self.evaluation_store = evaluation_store or EvaluationStore(self.project_root)
        self.config = config

    def resolve_target_and_binding(
        self,
        explicit_target: TargetSpec | None = None,
        explicit_binding: RuntimeCapabilityBinding | None = None,
    ) -> tuple[TargetSpec, RuntimeCapabilityBinding]:
        """Resolve target and capability binding from explicit args or project config."""
        target = explicit_target
        binding = explicit_binding

        if target is None:
            if self.config is not None:
                adapter_mode = str(self.config.runtime.adapter).lower()
                if adapter_mode in ("http", "http_json"):
                    endpoint = self.config.interface.endpoint or self.config.runtime.command
                    if not endpoint:
                        raise ConfigurationError(
                            "No HTTP endpoint configured in .viveka/config.yaml (interface.endpoint or runtime.command is empty).",
                            hint="Set interface.endpoint in .viveka/config.yaml or pass --target explicitly.",
                        )
                    opts = {
                        "method": self.config.interface.method,
                        "timeout_seconds": str(self.config.interface.timeout_seconds),
                        "allow_remote_target": str(
                            self.config.interface.allow_remote_target
                        ).lower(),
                        "max_response_bytes": str(self.config.interface.max_response_bytes),
                    }
                    if self.config.interface.auth_header_env:
                        opts["auth_header_env"] = self.config.interface.auth_header_env
                    if self.config.interface.healthcheck:
                        opts["healthcheck"] = self.config.interface.healthcheck

                    target = TargetSpec(
                        adapter_type=RuntimeAdapterType.HTTP,
                        endpoint=endpoint,
                        options=opts,
                    )
                elif adapter_mode in ("mcp",):
                    cmd = self.config.mcp.command or self.config.runtime.command
                    if not cmd:
                        raise ConfigurationError(
                            "No MCP server command configured in .viveka/config.yaml (mcp.command or runtime.command is empty).",
                            hint="Set mcp.command in .viveka/config.yaml or pass --target explicitly.",
                        )
                    import json

                    mcp_opts = {
                        "transport": self.config.mcp.transport,
                        "command": cmd,
                        "args": json.dumps(self.config.mcp.args),
                        "tool": self.config.mcp.tool,
                        "timeout_seconds": str(self.config.mcp.timeout_seconds),
                    }
                    if self.config.mcp.env_from_host:
                        mcp_opts["env_from_host"] = json.dumps(self.config.mcp.env_from_host)

                    target = TargetSpec(
                        adapter_type=RuntimeAdapterType.MCP,
                        options=mcp_opts,
                    )
                elif self.config.runtime.command:
                    target = TargetSpec(
                        adapter_type=RuntimeAdapterType.PYTHON_CALLABLE,
                        import_path=self.config.runtime.command,
                        working_directory=self.config.runtime.working_directory,
                    )
                else:
                    raise ConfigurationError(
                        "No runtime target configured in .viveka/config.yaml (runtime.command is empty). "
                        "Verification requires an explicit target agent configuration.",
                        hint="Set runtime.command in .viveka/config.yaml or pass --target explicitly.",
                    )
            else:
                raise ConfigurationError(
                    "No runtime target configured in .viveka/config.yaml (runtime.command is empty). "
                    "Verification requires an explicit target agent configuration.",
                    hint="Set runtime.command in .viveka/config.yaml or pass --target explicitly.",
                )

        if binding is None:
            if target.import_path == "viveka.demo.agent:run_demo_agent" or str(
                target.adapter_type
            ).lower() in ("http", "http_json", "mcp"):
                binding = get_demo_capability_binding()
            else:
                raise ConfigurationError(
                    f"No capability binding configured for target '{target.endpoint or target.import_path}'.",
                    hint="Define a RuntimeCapabilityBinding for the target tools.",
                )

        return target, binding

    def verify(
        self,
        property_filter: str | None = None,
        policy: ReproductionPolicy | None = None,
        budget: ReductionBudget | None = None,
        master_seed: int = 12345,
        max_worlds_per_property: int = 3,
        create_regression: bool = True,
        target_spec: TargetSpec | None = None,
        binding: RuntimeCapabilityBinding | None = None,
        enrich: bool = False,
        reasoning_provider: object | None = None,
    ) -> VerificationResult:
        """Execute verification over approved properties."""
        if self.property_store is None:
            raise ConfigurationError("PropertyStore not provided to VerificationEngine.")

        catalog = self.property_store.load_catalog()
        candidate_count = len(catalog.candidates)
        approved_props = catalog.approved

        # Filter by property if requested
        if property_filter:
            target_prop = self.property_store.get(property_filter) or catalog.by_stable_key(
                property_filter
            )
            if target_prop is None:
                raise ConfigurationError(
                    f"Property not found: '{property_filter}'.",
                    hint="Run `viveka properties list` to see available properties.",
                )
            if target_prop.status != PropertyStatus.APPROVED:
                raise ConfigurationError(
                    f"Property '{target_prop.id}' has status '{target_prop.status.value}'. "
                    "Only APPROVED properties can be verified.",
                    hint=f"Run `viveka properties approve {target_prop.id}` to approve it first.",
                )
            approved_props = [target_prop]

        if not approved_props:
            return VerificationResult(
                outcome=VerificationOutcome.NO_APPROVED_PROPERTIES,
                properties_considered=0,
                properties_verified=0,
                candidate_properties_count=candidate_count,
                summary_message=(
                    f"No approved properties found to verify ({candidate_count} candidate properties pending review). "
                    "Run `viveka properties list` and `viveka properties approve <ID>` to activate verification."
                ),
            )

        eff_target, eff_binding = self.resolve_target_and_binding(
            explicit_target=target_spec, explicit_binding=binding
        )

        eff_policy = policy or ReproductionPolicy(runs=5, minimum_violations=3)
        eff_budget = budget or ReductionBudget(max_candidates=10, max_trials=50)

        generator = WorldGenerator(seed=master_seed)
        reduction_engine = ReductionEngine(
            world_store=self.world_store,
            reduction_store=self.reduction_store,
            evaluation_store=self.evaluation_store,
        )
        diag_engine = DiagnosisEngine()
        regression_engine = RegressionEngine(
            property_store=self.property_store,
            world_store=self.world_store,
            reduction_store=self.reduction_store,
            diagnosis_store=self.diagnosis_store,
            regression_store=self.regression_store,
            evaluation_store=self.evaluation_store,
        )

        property_results: list[PropertyVerificationResult] = []
        total_worlds_tested = 0
        regressions_count = 0

        # Setup single shared advisory budget and enricher per verify session
        shared_reasoning_provider = reasoning_provider
        shared_enricher = None
        if enrich:
            if shared_reasoning_provider is None and self.config is not None:
                try:
                    from viveka.reasoning.factory import create_provider

                    shared_reasoning_provider = create_provider(self.config)
                except Exception:
                    shared_reasoning_provider = None

            if shared_reasoning_provider is not None:
                max_calls = 20
                if self.config is not None:
                    max_calls = self.config.reasoning.max_advisory_calls
                try:
                    from viveka.reasoning.advisors.diagnosis_enricher import DiagnosisEnricher
                    from viveka.reasoning.budget import AdvisoryBudget

                    shared_budget = AdvisoryBudget(max_calls=max_calls)
                    shared_enricher = DiagnosisEnricher(
                        shared_reasoning_provider,
                        budget=shared_budget,  # type: ignore[arg-type]
                    )
                except Exception:
                    shared_enricher = None

        for prop in approved_props:
            # Generate or load test worlds targeting this property
            worlds = []
            if self.world_store is not None:
                stored = [
                    w
                    for w in self.world_store.load_all()
                    if w.property_stable_key == prop.stable_key
                ]
                worlds.extend(stored[:max_worlds_per_property])

            if len(worlds) < max_worlds_per_property:
                gen_worlds = generator.generate_worlds(
                    [prop], max_worlds_per_property=max_worlds_per_property - len(worlds)
                )
                if self.world_store is not None:
                    for gw in gen_worlds:
                        self.world_store.save(gw)
                worlds.extend(gen_worlds)

            world_details: list[WorldVerificationDetail] = []
            prop_violated = False
            prop_errored = False
            last_reduction = None
            last_diag = None
            last_reg = None

            for w in worlds:
                total_worlds_tested += 1
                try:
                    repro = execute_reproduction(
                        property=prop,
                        world=w,
                        policy=eff_policy,
                        master_seed=master_seed,
                        seed_namespace=f"reduction:{w.id}",
                        binding=eff_binding,
                        target_spec=eff_target,
                        evaluation_store=self.evaluation_store,
                    )
                except Exception as exc:
                    prop_errored = True
                    world_details.append(
                        WorldVerificationDetail(
                            world_id=w.id,
                            reproduction=None,  # type: ignore
                            error_message=str(exc),
                        )
                    )
                    continue

                red_res = None
                diag_res = None
                reg_res = None

                if repro.criterion_met:
                    prop_violated = True
                    red_res = reduction_engine.reduce(
                        property_obj=prop,
                        world=w,
                        policy=eff_policy,
                        budget=eff_budget,
                        master_seed=master_seed,
                        binding=eff_binding,
                        target_spec=eff_target,
                    )
                    last_reduction = red_res

                    if red_res.final_reproduction.criterion_met:
                        diag_res = diag_engine.diagnose(
                            reduction_result=red_res,
                            property_obj=prop,
                            evaluation_store=self.evaluation_store,
                        )
                        if self.diagnosis_store is not None:
                            self.diagnosis_store.save(diag_res)
                        last_diag = diag_res

                        if create_regression:
                            reg_res = regression_engine.create(
                                reduction_result=red_res,
                                property_obj=prop,
                                diagnosis=diag_res,
                                original_world=w,
                            )
                            regressions_count += 1
                            last_reg = reg_res

                world_details.append(
                    WorldVerificationDetail(
                        world_id=w.id,
                        reproduction=repro,
                        reduction=red_res,
                        diagnosis=diag_res,
                        regression=reg_res,
                    )
                )

            # Determine property status
            if prop_errored and not world_details:
                p_status = PropertyVerificationStatus.ERROR
            elif prop_violated:
                p_status = PropertyVerificationStatus.REPRODUCED_VIOLATION
            elif prop_errored:
                p_status = PropertyVerificationStatus.ERROR
            elif world_details and all(
                wd.reproduction is not None
                and wd.reproduction.inconclusive_count == wd.reproduction.total_runs
                for wd in world_details
            ):
                p_status = PropertyVerificationStatus.INCONCLUSIVE
            else:
                p_status = PropertyVerificationStatus.NO_REPRODUCED_VIOLATION

            # Optional advisory diagnosis narrative enrichment
            advisory_narrative_text = None
            if enrich and last_diag is not None and shared_enricher is not None:
                try:
                    narrative_res, _ = shared_enricher.enrich(last_diag, prop)
                    advisory_narrative_text = narrative_res.narrative
                except Exception:
                    advisory_narrative_text = None

            property_results.append(
                PropertyVerificationResult(
                    property_id=prop.id,
                    property_name=prop.name,
                    property_stable_key=prop.stable_key,
                    property_revision=prop.revision,
                    status=p_status,
                    worlds_tested=len(world_details),
                    worlds_violated=sum(
                        1 for d in world_details if d.reproduction and d.reproduction.criterion_met
                    ),
                    world_details=world_details,
                    reduction_id=last_reduction.reduction_id if last_reduction else None,
                    diag_id=last_diag.diag_id if last_diag else None,
                    regression_id=last_reg.regression_id if last_reg else None,
                    advisory_narrative=advisory_narrative_text,
                )
            )

        # Determine overall outcome
        props_violated_count = sum(
            1
            for pr in property_results
            if pr.status == PropertyVerificationStatus.REPRODUCED_VIOLATION
        )
        props_passed_count = sum(
            1
            for pr in property_results
            if pr.status == PropertyVerificationStatus.NO_REPRODUCED_VIOLATION
        )
        props_errored_count = sum(
            1 for pr in property_results if pr.status == PropertyVerificationStatus.ERROR
        )

        if props_errored_count > 0:
            outcome = VerificationOutcome.INCOMPLETE
            summary = (
                f"Verification incomplete: {props_errored_count} of {len(property_results)} "
                f"approved properties encountered operational errors ({props_violated_count} with reproduced violations, "
                f"{props_passed_count} with no reproduced violations)."
            )
        elif props_violated_count > 0:
            outcome = VerificationOutcome.REPRODUCED_VIOLATIONS_FOUND
            summary = (
                f"Verification completed: {props_violated_count} of {len(property_results)} "
                f"approved properties produced reproduced violations across {total_worlds_tested} tested worlds."
            )
        else:
            outcome = VerificationOutcome.NO_REPRODUCED_VIOLATIONS
            summary = (
                f"Verification completed: No reproduced violations observed across {len(property_results)} "
                f"approved properties and {total_worlds_tested} tested worlds."
            )

        return VerificationResult(
            outcome=outcome,
            target_command=eff_target.import_path,
            properties_considered=len(approved_props),
            properties_verified=len(property_results),
            properties_passed=props_passed_count,
            properties_violated=props_violated_count,
            properties_errored=props_errored_count,
            total_worlds_tested=total_worlds_tested,
            regressions_created=regressions_count,
            candidate_properties_count=candidate_count,
            property_results=property_results,
            summary_message=summary,
        )
