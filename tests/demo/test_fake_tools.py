"""Tests for Phase 7 Demo fake tools and fixture interception."""

import pytest

from viveka.demo.tools import DemoToolStore, create_demo_tools
from viveka.runtime.collector import EventCollector
from viveka.runtime.models import (
    AgentDocumentContext,
    AgentEnvironmentContext,
    AgentRuntimeContext,
    AgentToolConfigContext,
)


def test_fake_tools_baseline_execution():
    ctx = AgentRuntimeContext(
        documents=[AgentDocumentContext(id="doc-1", content="Support policy content")]
    )
    collector = EventCollector()
    store = DemoToolStore()
    tools = create_demo_tools(ctx, collector, store)

    # 1. Search
    res_search = tools["knowledge.search"](query="policy")
    assert len(res_search["results"]) == 1

    # 2. Customer read
    res_cust = tools["customer.read"](customer_id="customer-42")
    assert res_cust["name"] == "Jane Doe"

    # 3. Refund create
    res_ref = tools["refund.create"](order_id="5832", amount=50.0)
    assert res_ref["status"] == "success"
    assert len(store.refunds) == 1

    # 4. Email send
    res_mail = tools["email.send"](recipient="user@example.com", subject="Sub", body="Body")
    assert res_mail["status"] == "sent"
    assert len(store.emails) == 1

    # Check collector sequence
    assert len(collector.events) == 8  # 4 tool calls + 4 tool results


def test_fake_tools_fixture_interception_network_down():
    ctx = AgentRuntimeContext(environment=AgentEnvironmentContext(network_available=False))
    collector = EventCollector()
    store = DemoToolStore()
    tools = create_demo_tools(ctx, collector, store)

    with pytest.raises(ConnectionError, match="Network unavailable"):
        tools["knowledge.search"](query="test")


def test_fake_tools_uncertain_retry_committed_write():
    # Configure refund.create to fail with timeout AFTER committing side effect
    ctx = AgentRuntimeContext(tools={"refund.create": AgentToolConfigContext(behavior="timeout")})
    collector = EventCollector()
    store = DemoToolStore()
    tools = create_demo_tools(ctx, collector, store)

    # Invocation 1: raises TimeoutError BUT side effect is committed in store.refunds
    with pytest.raises(TimeoutError, match="Connection lost after write committed"):
        tools["refund.create"](order_id="5832", amount=50.0)

    assert len(store.refunds) == 1  # Committed!

    # Invocation 2 (retry): raises TimeoutError AND commits second refund
    with pytest.raises(TimeoutError):
        tools["refund.create"](order_id="5832", amount=50.0)

    assert len(store.refunds) == 2  # Duplicate side effect committed!
