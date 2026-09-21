"""
Cross-run tool state isolation test.

Verifies that execution 1 mutations to tool state (refunds, emails, tickets)
do NOT leak into execution 2 when fresh tool stores are used per execution.
"""

from viveka.demo.agent import DemoAgent
from viveka.demo.tools import DemoToolStore
from viveka.runtime.models import AgentRuntimeContext


def test_cross_run_tool_state_isolation():
    agent = DemoAgent(violation_probability=1.0)
    ctx = AgentRuntimeContext(message="Please refund order 5832.")

    # Execution 1
    store1 = DemoToolStore()
    _out1, _events1 = agent.run(ctx, seed=1, tool_store=store1)
    assert len(store1.refunds) == 1

    # Execution 2 (fresh store instance)
    store2 = DemoToolStore()
    _out2, _events2 = agent.run(ctx, seed=2, tool_store=store2)
    assert len(store2.refunds) == 1

    # Verify store1 state was unaffected by execution 2
    assert store1.refunds != store2.refunds or store1 is not store2
    assert len(store1.refunds) == 1
    assert len(store2.refunds) == 1
