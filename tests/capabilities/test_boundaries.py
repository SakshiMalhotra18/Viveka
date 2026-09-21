"""Tests for viveka.capabilities.boundaries — trust boundary inference."""

from __future__ import annotations

from tests.capabilities.conftest import (
    make_call,
    make_function,
    make_import,
    make_module,
    make_static_result,
)
from viveka.capabilities.boundaries import infer_trust_boundaries
from viveka.capabilities.classifier import classify_capabilities


class TestTrustBoundaryInference:
    def test_empty_capabilities_no_boundaries(self) -> None:
        boundaries = infer_trust_boundaries([])
        assert boundaries == []

    def test_retrieval_produces_untrusted_ingress(self) -> None:
        func = make_function(
            "search_documents",
            calls=[make_call("similarity_search(", line=5)],
        )
        mod = make_module(
            "retriever.py",
            "retriever",
            functions=[func],
            imports=[make_import("langchain")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        boundaries = infer_trust_boundaries(caps)
        types = {b.boundary_type for b in boundaries}
        assert "untrusted_ingress" in types, f"Expected untrusted_ingress in {types}"

    def test_secret_access_produces_sensitive_source(self) -> None:
        func = make_function(
            "get_api_key",
            calls=[make_call("os.getenv(", line=3)],
        )
        mod = make_module(
            "config.py",
            "config",
            functions=[func],
            imports=[make_import("os")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        boundaries = infer_trust_boundaries(caps)
        types = {b.boundary_type for b in boundaries}
        assert "sensitive_source" in types

    def test_shell_execution_produces_privileged_sink(self) -> None:
        func = make_function(
            "run_command",
            calls=[make_call("subprocess.run(", line=5)],
        )
        mod = make_module(
            "exec.py",
            "exec_mod",
            functions=[func],
            imports=[make_import("subprocess")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        boundaries = infer_trust_boundaries(caps)
        types = {b.boundary_type for b in boundaries}
        assert "privileged_sink" in types

    def test_financial_write_produces_privileged_sink(self) -> None:
        func = make_function(
            "refund_order",
            calls=[make_call("stripe.refund(", line=5)],
        )
        mod = make_module(
            "billing.py",
            "billing",
            functions=[func],
            imports=[make_import("stripe")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        boundaries = infer_trust_boundaries(caps)
        types = {b.boundary_type for b in boundaries}
        assert "privileged_sink" in types

    def test_email_produces_external_sink(self) -> None:
        func = make_function(
            "send_notification",
            calls=[make_call("smtplib.SMTP(", line=5)],
        )
        mod = make_module(
            "mailer.py",
            "mailer",
            functions=[func],
            imports=[make_import("smtplib")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        boundaries = infer_trust_boundaries(caps)
        types = {b.boundary_type for b in boundaries}
        assert "external_sink" in types

    def test_all_boundaries_are_static_only(self) -> None:
        func = make_function(
            "process_refund",
            calls=[make_call("create_refund(", line=5)],
        )
        mod = make_module(
            "billing.py",
            "billing",
            functions=[func],
            imports=[make_import("stripe")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        boundaries = infer_trust_boundaries(caps)
        for boundary in boundaries:
            assert boundary.static_only is True, (
                f"Boundary {boundary.id} has static_only={boundary.static_only}, expected True"
            )

    def test_boundary_ids_are_unique(self) -> None:
        func1 = make_function("run_cmd", calls=[make_call("subprocess.run(", line=5)])
        func2 = make_function("search", calls=[make_call("similarity_search(", line=3)])
        mod = make_module(
            "mixed.py",
            "mixed",
            functions=[func1, func2],
            imports=[make_import("subprocess"), make_import("langchain")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        boundaries = infer_trust_boundaries(caps)
        ids = [b.id for b in boundaries]
        assert len(ids) == len(set(ids)), "Boundary IDs must be unique"

    def test_boundary_evidence_list_populated(self) -> None:
        func = make_function(
            "run_command",
            calls=[make_call("subprocess.run(", line=5)],
        )
        mod = make_module(
            "exec.py",
            "exec_mod",
            functions=[func],
            imports=[make_import("subprocess")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        boundaries = infer_trust_boundaries(caps)
        for b in boundaries:
            assert isinstance(b.evidence, list)
