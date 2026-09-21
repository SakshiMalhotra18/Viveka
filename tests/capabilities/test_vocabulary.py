"""Tests for viveka.capabilities.vocabulary — enum completeness and values."""

from __future__ import annotations

from viveka.capabilities.vocabulary import (
    CapabilityTag,
    Externality,
    Reversibility,
    SideEffect,
    TrustRole,
)


class TestCapabilityTag:
    def test_all_expected_tags_present(self) -> None:
        expected = {
            "filesystem_read",
            "filesystem_write",
            "filesystem_delete",
            "network_read",
            "network_write",
            "external_read",
            "external_write",
            "sensitive_read",
            "secret_access",
            "shell_execution",
            "code_execution",
            "database_read",
            "database_write",
            "communication",
            "financial_read",
            "financial_write",
            "read",
            "write",
            "retrieval",
            "untrusted_input",
            "authentication",
            "authorization",
            "side_effect",
            "destructive_write",
            "unknown",
        }
        actual = {tag.value for tag in CapabilityTag}
        assert expected == actual

    def test_tags_are_lowercase_strings(self) -> None:
        for tag in CapabilityTag:
            assert tag.value == tag.value.lower()
            assert tag.value == str(tag)

    def test_unknown_tag_exists(self) -> None:
        assert CapabilityTag.UNKNOWN == "unknown"


class TestSideEffect:
    def test_all_values(self) -> None:
        expected = {"none", "read_only", "mutating", "destructive", "unknown"}
        assert {v.value for v in SideEffect} == expected

    def test_unknown_is_valid(self) -> None:
        assert SideEffect.UNKNOWN == "unknown"


class TestExternality:
    def test_all_values(self) -> None:
        expected = {"local", "external", "unknown"}
        assert {v.value for v in Externality} == expected


class TestReversibility:
    def test_all_values(self) -> None:
        expected = {"reversible", "possibly_reversible", "irreversible", "unknown"}
        assert {v.value for v in Reversibility} == expected


class TestTrustRole:
    def test_all_values(self) -> None:
        expected = {
            "trusted_internal",
            "untrusted_ingress",
            "sensitive_source",
            "privileged_sink",
            "external_sink",
            "unknown",
        }
        assert {v.value for v in TrustRole} == expected

    def test_unknown_is_valid(self) -> None:
        assert TrustRole.UNKNOWN == "unknown"
