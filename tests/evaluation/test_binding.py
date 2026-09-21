"""Tests for RuntimeCapabilityBinding and demo binding provider."""

from viveka.evaluation.binding import get_demo_capability_binding
from viveka.evaluation.models import RuntimeCapabilityBinding


def test_runtime_capability_binding_lookup():
    binding = RuntimeCapabilityBinding(bindings={"src/tools.py::refund_order": "refund.create"})
    assert binding.resolve_tool("src/tools.py::refund_order") == "refund.create"
    assert binding.resolve_tool("src/unknown.py::fn") is None


def test_demo_capability_binding_provider():
    binding = get_demo_capability_binding()
    assert binding.resolve_tool("src/search.py::knowledge_search") == "knowledge.search"
    assert binding.resolve_tool("src/refund.py::refund_create") == "refund.create"
