"""
Reproduction runner protocol and default Phase 8 adapter for Phase 9 reduction engine.

Enables injecting stub runners for fast Phase 9 unit testing while consuming
the official Phase 8 execute_reproduction API in production.
"""

from __future__ import annotations

from typing import Protocol

from viveka.evaluation.models import (
    ReproductionPolicy,
    ReproductionResult,
    RuntimeCapabilityBinding,
)
from viveka.evaluation.reproduction import execute_reproduction
from viveka.evaluation.store import EvaluationStore
from viveka.properties.models import Property
from viveka.runtime.models import TargetSpec
from viveka.worlds.models import World


class ReproductionRunnerProtocol(Protocol):
    """Protocol for executing reproduction runs over a World."""

    def execute_reproduction(
        self,
        property: Property,
        world: World,
        policy: ReproductionPolicy | None = None,
        master_seed: int = 12345,
        seed_namespace: str | None = None,
        binding: RuntimeCapabilityBinding | None = None,
        target_spec: TargetSpec | None = None,
        evaluation_store: EvaluationStore | None = None,
    ) -> ReproductionResult:
        """Execute reproduction runs for world against property."""
        ...


class DefaultReproductionRunner:
    """Default runner delegating to Phase 8 execute_reproduction."""

    def execute_reproduction(
        self,
        property: Property,
        world: World,
        policy: ReproductionPolicy | None = None,
        master_seed: int = 12345,
        seed_namespace: str | None = None,
        binding: RuntimeCapabilityBinding | None = None,
        target_spec: TargetSpec | None = None,
        evaluation_store: EvaluationStore | None = None,
    ) -> ReproductionResult:
        return execute_reproduction(
            property=property,
            world=world,
            policy=policy,
            master_seed=master_seed,
            seed_namespace=seed_namespace,
            binding=binding,
            target_spec=target_spec,
            evaluation_store=evaluation_store,
        )
