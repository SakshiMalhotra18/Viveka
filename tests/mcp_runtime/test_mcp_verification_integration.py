"""
End-to-end verification engine integration tests for Phase 14 MCP runtime adapter.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from viveka.core.config import load_config
from viveka.evaluation.models import ReproductionPolicy
from viveka.properties.models import FailureHandledOracle, FlowForbiddenOracle, Property
from viveka.properties.store import PropertyStore
from viveka.properties.vocabulary import PropertyStatus
from viveka.runtime.models import TargetSpec
from viveka.runtime.vocabulary import RuntimeAdapterType
from viveka.verification.engine import VerificationEngine
from viveka.verification.vocabulary import PropertyVerificationStatus, VerificationOutcome

REF_SERVER = str((Path(__file__).parent / "reference_mcp_server.py").resolve())
PYTHON_EXE = sys.executable


def test_verification_engine_e2e_with_mcp_target(tmp_path: Path) -> None:
    """Verify end-to-end property verification using an explicit MCP TargetSpec."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    prop_store = PropertyStore(project_dir)
    prop = Property(
        id="VPROP-MCP-01",
        name="MCP Flow Forbidden",
        stable_key="PROP-MCP-01",
        description="Verify MCP flow forbidden property",
        status=PropertyStatus.APPROVED,
        oracle=FlowForbiddenOracle(
            untrusted_source_key="knowledge_search",
            forbidden_sink_key="refund_create",
        ),
    )
    prop_store.save(prop)

    mcp_target = TargetSpec(
        adapter_type=RuntimeAdapterType.MCP,
        options={
            "transport": "stdio",
            "command": PYTHON_EXE,
            "args": json.dumps([REF_SERVER]),
            "tool": "agent.run",
            "timeout_seconds": "10.0",
        },
    )

    engine = VerificationEngine(project_root=project_dir, property_store=prop_store)
    result = engine.verify(
        max_worlds_per_property=2,
        target_spec=mcp_target,
        policy=ReproductionPolicy(runs=2, minimum_violations=1),
    )

    # Output-only non-instrumented MCP target produces INCONCLUSIVE, outcome NO_REPRODUCED_VIOLATIONS
    assert result.outcome == VerificationOutcome.NO_REPRODUCED_VIOLATIONS
    assert result.properties_verified == 1
    assert result.property_results[0].status == PropertyVerificationStatus.INCONCLUSIVE
    assert result.total_worlds_tested == 2


def test_verification_engine_e2e_with_mcp_config(tmp_path: Path) -> None:
    """Verify end-to-end property verification loaded from .viveka/config.yaml."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    cfg_file = project_dir / ".viveka" / "config.yaml"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "runtime": {"adapter": "mcp"},
                "mcp": {
                    "transport": "stdio",
                    "command": PYTHON_EXE,
                    "args": [REF_SERVER],
                    "tool": "agent.run",
                    "timeout_seconds": 10.0,
                },
            }
        ),
        encoding="utf-8",
    )

    config = load_config(cfg_file)

    prop_store = PropertyStore(project_dir)
    prop = Property(
        id="VPROP-MCP-02",
        name="MCP Failure Handled Config",
        stable_key="PROP-MCP-02",
        description="Verify MCP failure handled property loaded from config",
        status=PropertyStatus.APPROVED,
        oracle=FailureHandledOracle(
            target_action_key="knowledge_search",
            must_not_represent_action_as_successful=True,
        ),
    )
    prop_store.save(prop)

    engine = VerificationEngine(project_root=project_dir, property_store=prop_store, config=config)
    result = engine.verify(
        max_worlds_per_property=1,
        policy=ReproductionPolicy(runs=2, minimum_violations=1),
    )

    assert result.outcome == VerificationOutcome.NO_REPRODUCED_VIOLATIONS
    assert result.properties_verified == 1
    assert result.property_results[0].status == PropertyVerificationStatus.INCONCLUSIVE
    assert result.total_worlds_tested == 1
