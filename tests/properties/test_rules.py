"""Tests for viveka.properties.rules — completeness, exact wording, and exposed-tool requirements."""

from __future__ import annotations

from viveka.properties.rules import PROPERTY_RULES, PROPERTY_RULES_BY_ID
from viveka.properties.vocabulary import InvariantType


class TestPropertyRulesRegistry:
    def test_all_expected_v1_rules_present(self) -> None:
        expected_ids = {
            "PROP-RULE-RET-FIN-001",
            "PROP-RULE-RET-SHELL-001",
            "PROP-RULE-RET-DEL-001",
            "PROP-RULE-SEC-EXT-001",
            "PROP-RULE-COMM-AUTH-001",
            "PROP-RULE-DB-UNTRUSTED-001",
            "PROP-RULE-FAIL-SILENT-001",
        }
        actual_ids = {r.id for r in PROPERTY_RULES}
        assert expected_ids == actual_ids
        assert set(PROPERTY_RULES_BY_ID.keys()) == expected_ids

    def test_read_only_purpose_rule_deferred_and_absent(self) -> None:
        assert "PROP-RULE-READONLY-PURPOSE-001" not in PROPERTY_RULES_BY_ID

    def test_failure_handling_exact_spec_wording(self) -> None:
        rule = PROPERTY_RULES_BY_ID["PROP-RULE-FAIL-SILENT-001"]
        assert rule.invariant_type == InvariantType.MUST_HANDLE_FAILURE
        assert (
            rule.description_template
            == "If a tool fails, the agent must not claim the action succeeded."
        )
        assert rule.requires_exposed_tool is True

    def test_no_arbitrary_severity_scores_on_rules(self) -> None:
        for rule in PROPERTY_RULES:
            assert not hasattr(rule, "severity")
