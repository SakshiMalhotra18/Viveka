"""
Runtime capability binding provider for VIVEKA Phase 8.

Maps Phase 5 path-qualified stable capability keys ({path}::{symbol}) to target
runtime tool names without fuzzy or symbol-string guessing.
"""

from __future__ import annotations

from viveka.evaluation.models import RuntimeCapabilityBinding


def get_demo_capability_binding() -> RuntimeCapabilityBinding:
    """Return explicit V1 binding for the bundled demo agent.

    Maps demo static capability keys to demo runtime tool names.
    """
    return RuntimeCapabilityBinding(
        bindings={
            # Ingress source capabilities
            "src/search.py::knowledge_search": "knowledge.search",
            "src/tools.py::search_docs": "knowledge.search",
            "src/read.py::search": "knowledge.search",
            "src/read.py::read": "knowledge.search",
            "src/customer.py::customer_read": "customer.read",
            "src/tools.py::customer_read": "customer.read",
            # Egress / sink capabilities
            "src/refund.py::refund_create": "refund.create",
            "src/payment.py::refund_order": "refund.create",
            "src/pay.py::refund": "refund.create",
            "src/tools.py::refund_order": "refund.create",
            "src/tools.py::refund_create": "refund.create",
            "src/tools.py::delete_account": "refund.create",
            "src/email.py::email_send": "email.send",
            "src/tools.py::email_send": "email.send",
            "src/ticket.py::ticket_update": "ticket.update",
            "src/tools.py::ticket_update": "ticket.update",
        }
    )
