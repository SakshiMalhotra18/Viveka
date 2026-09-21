"""Tests for viveka.properties.vocabulary — completeness and string values."""

from __future__ import annotations

from viveka.properties.vocabulary import (
    InvariantType,
    PropertyEvidenceType,
    PropertySource,
    PropertyStatus,
)


class TestPropertyStatus:
    def test_all_expected_statuses_present(self) -> None:
        expected = {"candidate", "approved", "rejected", "disabled", "deprecated"}
        actual = {s.value for s in PropertyStatus}
        assert expected == actual


class TestPropertySource:
    def test_all_expected_sources_present(self) -> None:
        expected = {
            "rule-derived",
            "code-derived",
            "user-authored",
            "regression-derived",
            "model-assisted",
        }
        actual = {s.value for s in PropertySource}
        assert expected == actual


class TestInvariantType:
    def test_all_expected_invariants_present(self) -> None:
        expected = {
            "forbidden_flow",
            "must_handle_failure",
        }
        actual = {i.value for i in InvariantType}
        assert expected == actual


class TestPropertyEvidenceType:
    def test_all_expected_evidence_types_present(self) -> None:
        expected = {
            "capability",
            "trust_boundary",
            "graph_path",
            "static_call",
        }
        actual = {e.value for e in PropertyEvidenceType}
        assert expected == actual
