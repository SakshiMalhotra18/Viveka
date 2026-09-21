"""
Tests for viveka.capabilities.classifier — false-positive suppression.

These tests verify that the classifier does NOT incorrectly flag:
  - refund_policy_text() — documentation function, no live capability
  - delete_label()       — label management, not filesystem delete
  - execute_plan()       — planning function, not code execution
  - os.getenv("APP_ENV") — config read, not a secret (still allowed but tested)

NOTE: VIVEKA prefers false positives over false negatives for safety.
Some of these cases may still produce capabilities when evidence is
ambiguous — this file tests the strict false-positive cases only.
"""

from __future__ import annotations

from tests.capabilities.conftest import (
    make_call,
    make_function,
    make_import,
    make_module,
    make_static_result,
)
from viveka.capabilities.classifier import classify_capabilities
from viveka.capabilities.vocabulary import CapabilityTag


class TestFalsePositives:
    def test_refund_policy_text_no_real_capability(self) -> None:
        """A function named 'refund_policy_text' with no real calls should not produce
        a financial_write capability (it's documentation, not a live refund)."""
        func = make_function(
            "refund_policy_text",
            calls=[],  # No actual refund() calls
        )
        mod = make_module(
            "docs.py",
            "docs",
            functions=[func],
            imports=[],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        financial_caps = [c for c in caps if CapabilityTag.FINANCIAL_WRITE in c.tags]
        assert not financial_caps, (
            f"Expected no financial_write caps for 'refund_policy_text' with no calls, "
            f"got: {financial_caps}"
        )

    def test_delete_label_no_filesystem_delete(self) -> None:
        """delete_label() with no filesystem call evidence should not trigger
        the RULE-FS-DEL-001 filesystem_delete capability."""
        func = make_function(
            name="delete_label",
            qualified_name="delete_label",
            calls=[],  # No os.remove(), no unlink(), etc.
        )
        mod = make_module(
            "labels.py",
            "labels",
            functions=[func],
            imports=[],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        fs_del_caps = [c for c in caps if CapabilityTag.FILESYSTEM_DELETE in c.tags]
        assert not fs_del_caps, (
            f"Expected no filesystem_delete cap for 'delete_label' with no calls, "
            f"got: {fs_del_caps}"
        )

    def test_execute_plan_not_code_execution(self) -> None:
        """execute_plan() with no eval/exec calls should not trigger
        the RULE-PROC-EVAL-001 code_execution capability."""
        func = make_function(
            name="execute_plan",
            qualified_name="execute_plan",
            calls=[make_call("plan.steps(", line=5)],  # Not eval() or exec()
        )
        mod = make_module(
            "planner.py",
            "planner",
            functions=[func],
            imports=[],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        exec_caps = [c for c in caps if CapabilityTag.CODE_EXECUTION in c.tags]
        assert not exec_caps, (
            f"Expected no code_execution cap for 'execute_plan' without eval/exec calls, "
            f"got: {exec_caps}"
        )

    def test_real_refund_with_stripe_import_is_detected(self) -> None:
        """Sanity check: a real refund function WITH stripe import and refund() call
        MUST produce financial_write — this verifies false-positive guard doesn't
        suppress legitimate capabilities."""
        func = make_function(
            "process_refund",
            calls=[make_call("stripe.refunds.create(", line=10)],
        )
        mod = make_module(
            "billing.py",
            "billing",
            functions=[func],
            imports=[make_import("stripe")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        tags = {str(t) for c in caps for t in c.tags}
        assert "financial_write" in tags, (
            "Expected financial_write to be detected for real refund function with stripe import"
        )

    def test_real_delete_with_os_remove_is_detected(self) -> None:
        """Sanity check: a function with actual os.remove() call MUST produce
        filesystem_delete — this verifies guard doesn't suppress real deletes."""
        func = make_function(
            "cleanup_tmp_files",
            calls=[make_call("os.remove(", line=5)],
        )
        mod = make_module(
            "cleanup.py",
            "cleanup",
            functions=[func],
            imports=[make_import("os")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        tags = {str(t) for c in caps for t in c.tags}
        assert "filesystem_delete" in tags
