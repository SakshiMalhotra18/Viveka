"""Tests for viveka.capabilities.classifier — full classification scenarios."""

from __future__ import annotations

from tests.capabilities.conftest import (
    make_call,
    make_function,
    make_import,
    make_module,
    make_static_result,
)
from viveka.capabilities.classifier import classify_capabilities
from viveka.capabilities.vocabulary import (
    CapabilityTag,
    TrustRole,
)


def _tags(caps) -> set[str]:
    """Flatten all capability tags to a set of strings."""
    result: set[str] = set()
    for cap in caps:
        result.update(str(t) for t in cap.tags)
    return result


class TestFilesystemCapabilities:
    def test_read_file_detected_via_call(self) -> None:
        func = make_function(
            "load_document",
            calls=[make_call("open(", line=5), make_call("read(", line=6)],
        )
        mod = make_module("reader.py", "reader", functions=[func])
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        assert any(CapabilityTag.FILESYSTEM_READ in cap.tags for cap in caps)

    def test_write_file_detected_via_call(self) -> None:
        func = make_function(
            "save_output",
            calls=[make_call("write_text(", line=7)],
        )
        mod = make_module("writer.py", "writer", functions=[func])
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        assert any(CapabilityTag.FILESYSTEM_WRITE in cap.tags for cap in caps)

    def test_delete_file_detected_via_os_remove(self) -> None:
        func = make_function(
            "purge_temp",
            calls=[make_call("os.remove(", line=4)],
        )
        mod = make_module(
            "cleanup.py",
            "cleanup",
            functions=[func],
            imports=[make_import("os")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        tags = _tags(caps)
        assert "filesystem_delete" in tags
        assert "destructive_write" in tags


class TestNetworkCapabilities:
    def test_network_read_via_requests_get(self) -> None:
        func = make_function(
            "fetch_data",
            calls=[make_call("requests.get(", line=5)],
        )
        mod = make_module(
            "fetcher.py",
            "fetcher",
            functions=[func],
            imports=[make_import("requests")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        assert any(CapabilityTag.NETWORK_READ in cap.tags for cap in caps)

    def test_network_write_via_requests_post(self) -> None:
        func = make_function(
            "submit_data",
            calls=[make_call("requests.post(", line=8)],
        )
        mod = make_module(
            "sender.py",
            "sender",
            functions=[func],
            imports=[make_import("requests")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        assert any(CapabilityTag.NETWORK_WRITE in cap.tags for cap in caps)


class TestShellCapabilities:
    def test_shell_execution_via_subprocess(self) -> None:
        func = make_function(
            "run_shell_cmd",
            calls=[make_call("subprocess.run(", line=5)],
        )
        mod = make_module(
            "executor.py",
            "executor",
            functions=[func],
            imports=[make_import("subprocess")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        tags = _tags(caps)
        assert "shell_execution" in tags

    def test_shell_execution_trust_role_is_privileged_sink(self) -> None:
        func = make_function(
            "run_shell_cmd",
            calls=[make_call("subprocess.run(", line=5)],
        )
        mod = make_module(
            "executor.py",
            "executor",
            functions=[func],
            imports=[make_import("subprocess")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        shell_caps = [c for c in caps if CapabilityTag.SHELL_EXECUTION in c.tags]
        assert shell_caps
        assert all(c.trust_role == TrustRole.PRIVILEGED_SINK for c in shell_caps)


class TestFinancialCapabilities:
    def test_financial_refund_detected(self) -> None:
        func = make_function(
            "refund_order",
            calls=[make_call("stripe.refund(", line=10)],
        )
        mod = make_module(
            "billing.py",
            "billing",
            functions=[func],
            imports=[make_import("stripe")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        tags = _tags(caps)
        assert "financial_write" in tags

    def test_financial_refund_is_irreversible(self) -> None:
        func = make_function(
            "refund_order",
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
        fin_caps = [c for c in caps if CapabilityTag.FINANCIAL_WRITE in c.tags]
        assert fin_caps
        assert all(c.reversibility.value == "irreversible" for c in fin_caps)


class TestSecretCapabilities:
    def test_secret_env_access_detected(self) -> None:
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
        tags = _tags(caps)
        assert "secret_access" in tags or "sensitive_read" in tags


class TestCodeExecutionCapabilities:
    def test_eval_detected(self) -> None:
        func = make_function(
            "run_expression",
            calls=[make_call("eval(", line=5)],
        )
        mod = make_module("dynamic.py", "dynamic", functions=[func])
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        tags = _tags(caps)
        assert "code_execution" in tags


class TestDatabaseCapabilities:
    def test_db_write_detected(self) -> None:
        func = make_function(
            "save_user",
            calls=[make_call("session.add(", line=7), make_call("session.commit(", line=8)],
        )
        mod = make_module(
            "db.py",
            "db",
            functions=[func],
            imports=[make_import("sqlalchemy")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        tags = _tags(caps)
        assert "database_write" in tags

    def test_db_read_detected(self) -> None:
        func = make_function(
            "get_user",
            calls=[make_call(".filter(", line=5), make_call(".fetchall(", line=6)],
        )
        mod = make_module(
            "db.py",
            "db",
            functions=[func],
            imports=[make_import("sqlalchemy")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        tags = _tags(caps)
        assert "database_read" in tags


class TestCapabilityIdFormat:
    def test_capability_ids_have_vcap_prefix(self) -> None:
        func = make_function(
            "delete_all",
            calls=[make_call("os.remove(", line=4)],
        )
        mod = make_module(
            "cleanup.py",
            "cleanup",
            functions=[func],
            imports=[make_import("os")],
        )
        result = make_static_result(modules=[mod])
        caps, _ = classify_capabilities(result)
        for cap in caps:
            assert cap.id.startswith("VCAP-"), f"Bad ID format: {cap.id}"


class TestStatistics:
    def test_statistics_total_matches_capability_count(self) -> None:
        func = make_function(
            "run_cmd",
            calls=[make_call("subprocess.run(", line=5)],
        )
        mod = make_module(
            "exec.py",
            "exec",
            functions=[func],
            imports=[make_import("subprocess")],
        )
        result = make_static_result(modules=[mod])
        caps, stats = classify_capabilities(result)
        assert stats.total_capabilities == len(caps)

    def test_statistics_by_tag_populated(self) -> None:
        func = make_function(
            "delete_file",
            calls=[make_call("os.remove(", line=5)],
        )
        mod = make_module(
            "cleanup.py",
            "cleanup",
            functions=[func],
            imports=[make_import("os")],
        )
        result = make_static_result(modules=[mod])
        _, stats = classify_capabilities(result)
        assert len(stats.by_tag) > 0

    def test_empty_result_produces_empty_capabilities(self) -> None:
        result = make_static_result(modules=[])
        caps, stats = classify_capabilities(result)
        assert caps == []
        assert stats.total_capabilities == 0
