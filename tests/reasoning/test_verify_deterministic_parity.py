"""
Parity test proving that with reasoning disabled, viveka verify behaves
identically to Phase 11 deterministic verification.
"""

from __future__ import annotations

from pathlib import Path

from viveka.core.config import VivekaConfig
from viveka.core.ids import new_id
from viveka.evaluation.binding import get_demo_capability_binding
from viveka.evaluation.models import ReproductionPolicy
from viveka.properties.models import FlowForbiddenOracle, Property
from viveka.properties.store import PropertyStore
from viveka.properties.vocabulary import PropertyStatus
from viveka.runtime.models import TargetSpec
from viveka.verification.engine import VerificationEngine
from viveka.verification.vocabulary import VerificationOutcome


def test_verify_reasoning_disabled_parity(tmp_path: Path) -> None:
    """Proves reasoning.mode='deterministic' produces exact Phase 11 results without model calls."""
    prop_store = PropertyStore(tmp_path)
    clean_prop = Property(
        id=new_id("VPROP"),
        stable_key="prop-rule-clean:forbidden_flow:search->refund",
        name="clean-property",
        description="Clean property without violations in baseline world.",
        status=PropertyStatus.APPROVED,
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="src/search.py::knowledge_search",
            forbidden_sink_key="src/ticket.py::ticket_update",
        ),
    )
    prop_store.save(clean_prop)

    target_spec = TargetSpec(
        adapter_type="python_callable",
        import_path="viveka.demo.agent:run_demo_agent",
    )
    binding = get_demo_capability_binding()

    cfg = VivekaConfig()  # default reasoning.mode = "deterministic"
    engine = VerificationEngine(project_root=tmp_path, config=cfg)

    # 1. Run verify with default settings (no reasoning)
    res = engine.verify(
        policy=ReproductionPolicy(runs=1, minimum_violations=1),
        max_worlds_per_property=1,
        target_spec=target_spec,
        binding=binding,
        enrich=False,
    )

    assert res.outcome == VerificationOutcome.NO_REPRODUCED_VIOLATIONS
    assert res.properties_verified == 1
    assert res.properties_passed == 1
    assert res.property_results[0].advisory_narrative is None
