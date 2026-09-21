"""Tests for viveka.capabilities.rules — rule registry completeness and individual rules."""

from __future__ import annotations

from viveka.capabilities.rules import RULES, RULES_BY_ID
from viveka.capabilities.vocabulary import CapabilityTag, Externality, SideEffect, TrustRole

EXPECTED_RULE_IDS = {
    "RULE-FS-READ-001",
    "RULE-FS-WRITE-001",
    "RULE-FS-DEL-001",
    "RULE-PROC-SHELL-001",
    "RULE-PROC-EVAL-001",
    "RULE-NET-GET-001",
    "RULE-NET-POST-001",
    "RULE-COMM-EMAIL-001",
    "RULE-FIN-REFUND-001",
    "RULE-FIN-PAY-001",
    "RULE-RET-SEARCH-001",
    "RULE-SEC-ENV-001",
    "RULE-DB-WRITE-001",
    "RULE-DB-READ-001",
    "RULE-FALLBACK-001",
}


class TestRuleRegistry:
    def test_all_expected_rules_present(self) -> None:
        actual = {r.id for r in RULES}
        assert actual == EXPECTED_RULE_IDS

    def test_rules_by_id_index_complete(self) -> None:
        assert set(RULES_BY_ID.keys()) == EXPECTED_RULE_IDS

    def test_no_duplicate_ids(self) -> None:
        ids = [r.id for r in RULES]
        assert len(ids) == len(set(ids))

    def test_all_rules_have_explanation(self) -> None:
        for rule in RULES:
            assert rule.explanation, f"Rule {rule.id} has no explanation"

    def test_all_rules_produce_at_least_one_tag(self) -> None:
        for rule in RULES:
            assert len(rule.produced_tags) >= 1, f"Rule {rule.id} produces no tags"

    def test_fallback_rule_produces_unknown_tag(self) -> None:
        fallback = RULES_BY_ID["RULE-FALLBACK-001"]
        assert CapabilityTag.UNKNOWN in fallback.produced_tags

    def test_fallback_rule_has_unknown_confidence(self) -> None:
        fallback = RULES_BY_ID["RULE-FALLBACK-001"]
        assert fallback.confidence == "low"


class TestSpecificRules:
    def test_fs_read_is_read_only(self) -> None:
        rule = RULES_BY_ID["RULE-FS-READ-001"]
        assert rule.side_effect == SideEffect.READ_ONLY
        assert rule.externality == Externality.LOCAL
        assert CapabilityTag.FILESYSTEM_READ in rule.produced_tags

    def test_fs_delete_is_destructive(self) -> None:
        rule = RULES_BY_ID["RULE-FS-DEL-001"]
        assert rule.side_effect == SideEffect.DESTRUCTIVE
        assert CapabilityTag.DESTRUCTIVE_WRITE in rule.produced_tags
        assert CapabilityTag.FILESYSTEM_DELETE in rule.produced_tags
        assert rule.reversibility.value == "irreversible"

    def test_shell_execution_is_privileged_sink(self) -> None:
        rule = RULES_BY_ID["RULE-PROC-SHELL-001"]
        assert rule.trust_role == TrustRole.PRIVILEGED_SINK
        assert CapabilityTag.SHELL_EXECUTION in rule.produced_tags

    def test_eval_rule_is_privileged_sink(self) -> None:
        rule = RULES_BY_ID["RULE-PROC-EVAL-001"]
        assert rule.trust_role == TrustRole.PRIVILEGED_SINK
        assert CapabilityTag.CODE_EXECUTION in rule.produced_tags

    def test_net_get_is_external_untrusted_ingress(self) -> None:
        rule = RULES_BY_ID["RULE-NET-GET-001"]
        assert rule.externality == Externality.EXTERNAL
        assert rule.trust_role == TrustRole.UNTRUSTED_INGRESS
        assert CapabilityTag.NETWORK_READ in rule.produced_tags

    def test_net_post_is_external_sink(self) -> None:
        rule = RULES_BY_ID["RULE-NET-POST-001"]
        assert rule.trust_role == TrustRole.EXTERNAL_SINK
        assert CapabilityTag.NETWORK_WRITE in rule.produced_tags

    def test_financial_refund_is_irreversible(self) -> None:
        rule = RULES_BY_ID["RULE-FIN-REFUND-001"]
        assert rule.reversibility.value == "irreversible"
        assert CapabilityTag.FINANCIAL_WRITE in rule.produced_tags
        assert rule.trust_role == TrustRole.PRIVILEGED_SINK

    def test_secret_env_is_sensitive_source(self) -> None:
        rule = RULES_BY_ID["RULE-SEC-ENV-001"]
        assert rule.trust_role == TrustRole.SENSITIVE_SOURCE
        assert CapabilityTag.SECRET_ACCESS in rule.produced_tags

    def test_db_write_is_mutating(self) -> None:
        rule = RULES_BY_ID["RULE-DB-WRITE-001"]
        assert rule.side_effect == SideEffect.MUTATING
        assert CapabilityTag.DATABASE_WRITE in rule.produced_tags

    def test_db_read_is_sensitive_source(self) -> None:
        rule = RULES_BY_ID["RULE-DB-READ-001"]
        assert rule.trust_role == TrustRole.SENSITIVE_SOURCE
        assert CapabilityTag.DATABASE_READ in rule.produced_tags

    def test_retrieval_is_untrusted_ingress(self) -> None:
        rule = RULES_BY_ID["RULE-RET-SEARCH-001"]
        assert rule.trust_role == TrustRole.UNTRUSTED_INGRESS
        assert CapabilityTag.RETRIEVAL in rule.produced_tags

    def test_communication_is_irreversible_external_sink(self) -> None:
        rule = RULES_BY_ID["RULE-COMM-EMAIL-001"]
        assert rule.trust_role == TrustRole.EXTERNAL_SINK
        assert rule.reversibility.value == "irreversible"
        assert CapabilityTag.COMMUNICATION in rule.produced_tags
