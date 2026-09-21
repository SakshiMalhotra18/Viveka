"""
Controlled vocabularies and constants for the VIVEKA Demo Customer Support Agent.
"""

from __future__ import annotations

from enum import StrEnum


class VulnerabilityScenario(StrEnum):
    """Vulnerability scenarios exhibited by the demo customer support agent."""

    INDIRECT_PROMPT_INJECTION = "indirect_prompt_injection"
    UNAUTHORIZED_REFUND = "unauthorized_refund"
    SENSITIVE_DATA_EXFILTRATION = "sensitive_data_exfiltration"
    FALSE_SUCCESS_AFTER_FAILURE = "false_success_after_failure"
    DUPLICATE_SIDE_EFFECT = "duplicate_side_effect"
