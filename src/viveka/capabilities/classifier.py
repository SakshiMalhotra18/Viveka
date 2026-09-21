"""
Static capability classifier for VIVEKA Phase 4.

Evaluates deterministic :class:`~viveka.capabilities.rules.CapabilityRule` s
against Phase 3 :class:`~viveka.inspection.python_models.StaticAnalysisResult`
to produce a list of :class:`~viveka.capabilities.models.Capability` objects.

Design constraints:
  - No LLMs.  No network.  No target code execution.
  - Matching is string-substring only — deliberate simplicity.
  - ``unknown`` is always preferred over a wrong label.
  - False-positive controls are baked in (see :func:`_is_false_positive`).
"""

from __future__ import annotations

import re
from collections import defaultdict

from viveka.capabilities.models import Capability, CapabilityEvidence, CapabilityStatistics
from viveka.capabilities.rules import RULES, CapabilityRule
from viveka.capabilities.vocabulary import CapabilityTag
from viveka.core.ids import new_id
from viveka.inspection.python_models import (
    PythonFunction,
    PythonModule,
    StaticAnalysisResult,
)

# ---------------------------------------------------------------------------
# False-positive guard patterns
# ---------------------------------------------------------------------------

# Patterns whose presence in a *function name* strongly suggests the symbol
# is about documentation, policy, or test — NOT a live operational capability.
_FP_NAME_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in [
        r"(policy|document|doc|readme|label|text|string|template|example|fixture|dummy|mock|fake|stub|test_|_test)",
    ]
)

# Call expressions that look like capability-relevant calls but are actually
# common non-capability uses when the symbol name suggests it's a string/label.
_FP_SAFE_CALL_FRAGMENTS: frozenset[str] = frozenset(
    {
        # Common string/text operations that aren't real capabilities
        "str.",
        "label",
        "template",
        "format",
        "print",
        "log",
        "logger",
        "logging",
    }
)

# Environment variable patterns that are typically config reads, not secrets
_FP_ENV_SAFE_NAMES: frozenset[str] = frozenset(
    {
        "APP_ENV",
        "ENVIRONMENT",
        "ENV",
        "DEBUG",
        "LOG_LEVEL",
        "LOG_FORMAT",
        "PYTHONPATH",
        "PATH",
        "HOME",
        "USER",
        "LANG",
        "LOCALE",
        "TZ",
        "TIMEZONE",
        "PORT",
        "HOST",
        "WORKERS",
    }
)

# Name fragments that, in isolation, are not enough to classify as "delete"
# without corroborating call evidence
_FP_DELETE_LABEL_NAMES: frozenset[str] = frozenset(
    {
        "delete_label",
        "remove_tag",
        "delete_tag",
        "untag",
        "remove_flag",
    }
)

# Name fragments that suggest planning / description rather than execution
_FP_EXECUTION_PLAN_NAMES: frozenset[str] = frozenset(
    {
        "execute_plan",
        "execution_plan",
        "plan_executor",
        "run_plan",
    }
)


def _is_false_positive(
    func: PythonFunction,
    rule: CapabilityRule,
    call_ev: list[CapabilityEvidence],
    evidence_values: list[str],
) -> bool:
    """Return True if this (function, rule) pairing is a likely false positive.

    Conservative: we only suppress when we have high confidence the match
    is spurious.  When uncertain, we keep the capability (prefer false
    positives over false negatives for safety-oriented analysis).
    """
    fname = func.name.lower()
    qname = func.qualified_name.lower()

    # Policy / documentation functions — names that strongly suggest text content
    for pat in _FP_NAME_PATTERNS:
        if pat.search(fname):
            # Only allow if rule is corroborated by a real, operational call pattern
            call_values = [e.value for e in call_ev]
            if not any(
                cv
                for cv in call_values
                if not any(safe in cv.lower() for safe in _FP_SAFE_CALL_FRAGMENTS)
            ):
                return True

    # Secret/env access: suppress if the env var name is a common config var
    if rule.id == "RULE-SEC-ENV-001":
        secret_looking = False
        for call in func.calls:
            callee = call.callee
            for safe in _FP_ENV_SAFE_NAMES:
                if safe in callee.upper():
                    pass
                else:
                    secret_looking = True
        if not secret_looking and not evidence_values:
            return True

    # Delete label / tag operations — name-only match without call evidence
    if rule.id == "RULE-FS-DEL-001" and qname in _FP_DELETE_LABEL_NAMES:
        call_values = [e.value for e in call_ev]
        if not any(
            pat in cv
            for cv in call_values
            for pat in (
                "os.remove",
                "os.unlink",
                "shutil.rmtree",
                "Path.unlink",
                ".unlink(",
                "rmtree",
            )
        ):
            return True

    # "execute_plan" style names — planning functions, not code execution
    if rule.id == "RULE-PROC-EVAL-001" and qname in _FP_EXECUTION_PLAN_NAMES:
        call_values = [e.value for e in call_ev]
        if not any("eval(" in cv or "exec(" in cv for cv in call_values):
            return True

    return False


# ---------------------------------------------------------------------------
# Evidence extractors
# ---------------------------------------------------------------------------


def _collect_call_evidence(
    func: PythonFunction,
    patterns: tuple[str, ...],
    file_path: str,
) -> list[CapabilityEvidence]:
    """Extract CapabilityEvidence from calls inside ``func`` matching ``patterns``."""
    evidence: list[CapabilityEvidence] = []
    for call in func.calls:
        for pat in patterns:
            if pat.lower() in call.callee.lower():
                evidence.append(
                    CapabilityEvidence(
                        evidence_type="call",
                        value=call.callee,
                        file_path=file_path,
                        line=call.line,
                        weight=0.9,
                    )
                )
                break  # one evidence per call
    return evidence


def _collect_import_evidence(
    module: PythonModule,
    patterns: tuple[str, ...],
) -> list[CapabilityEvidence]:
    """Extract CapabilityEvidence from module imports matching ``patterns``."""
    evidence: list[CapabilityEvidence] = []
    seen: set[str] = set()
    for imp in module.imports:
        for pat in patterns:
            if pat.lower() in imp.module.lower() and imp.module not in seen:
                seen.add(imp.module)
                evidence.append(
                    CapabilityEvidence(
                        evidence_type="import",
                        value=imp.module,
                        file_path=module.path,
                        line=imp.line,
                        weight=0.6,
                    )
                )
                break
    return evidence


def _collect_name_evidence(
    func: PythonFunction,
    patterns: tuple[str, ...],
    file_path: str,
) -> list[CapabilityEvidence]:
    """Extract CapabilityEvidence from function name matching ``patterns``."""
    evidence: list[CapabilityEvidence] = []
    for pat in patterns:
        if pat.lower() in func.name.lower():
            evidence.append(
                CapabilityEvidence(
                    evidence_type="name_match",
                    value=func.name,
                    file_path=file_path,
                    line=func.line_start,
                    weight=0.4,
                )
            )
            break
    return evidence


def _collect_decorator_evidence(
    func: PythonFunction,
    patterns: tuple[str, ...],
    file_path: str,
) -> list[CapabilityEvidence]:
    """Extract CapabilityEvidence from function decorators matching ``patterns``."""
    evidence: list[CapabilityEvidence] = []
    for dec in func.decorators:
        for pat in patterns:
            if pat.lower() in dec.name.lower():
                evidence.append(
                    CapabilityEvidence(
                        evidence_type="decorator",
                        value=dec.name,
                        file_path=file_path,
                        line=dec.line,
                        weight=0.7,
                    )
                )
                break
    return evidence


# ---------------------------------------------------------------------------
# Confidence score
# ---------------------------------------------------------------------------

_CONFIDENCE_THRESHOLDS = {
    "high": 0.7,
    "medium": 0.35,
    "low": 0.0,
}


def _score_to_confidence(score: float) -> str:
    if score >= _CONFIDENCE_THRESHOLDS["high"]:
        return "high"
    if score >= _CONFIDENCE_THRESHOLDS["medium"]:
        return "medium"
    return "low"


def _evidence_score(evidence: list[CapabilityEvidence]) -> float:
    if not evidence:
        return 0.0
    return min(1.0, sum(e.weight for e in evidence) / max(1, len(evidence)) + 0.1 * len(evidence))


# ---------------------------------------------------------------------------
# Function-level classification
# ---------------------------------------------------------------------------


def _classify_function(
    func: PythonFunction,
    module: PythonModule,
    is_tool_candidate: bool,
) -> list[Capability]:
    """Classify a single function against all rules."""
    capabilities: list[Capability] = []

    for rule in RULES:
        if rule.id == "RULE-FALLBACK-001":
            continue  # applied separately after all other rules

        # Gather evidence for this rule against this function
        call_ev = _collect_call_evidence(func, rule.call_patterns, module.path)
        import_ev = _collect_import_evidence(module, rule.import_patterns)
        name_ev = _collect_name_evidence(func, rule.name_patterns, module.path)
        dec_ev = _collect_decorator_evidence(func, rule.decorator_patterns, module.path)

        # A function must have function-level evidence (call, name, or decorator).
        # Module-level imports alone cannot attribute a capability to an arbitrary function.
        if not (call_ev or name_ev or dec_ev):
            continue

        all_evidence = call_ev + import_ev + name_ev + dec_ev
        if not all_evidence:
            continue

        # False-positive guard
        evidence_values = [e.value for e in all_evidence]
        if _is_false_positive(func, rule, call_ev, evidence_values):
            continue

        score = _evidence_score(all_evidence)
        final_confidence = _score_to_confidence(score)

        cap = Capability(
            id=new_id("VCAP"),
            name=_capability_name(func.name, rule),
            source_symbol=func.qualified_name,
            source_file=module.path,
            source_line=func.line_start,
            tags=list(rule.produced_tags),
            confidence=final_confidence,
            evidence=all_evidence,
            side_effect=rule.side_effect,
            externality=rule.externality,
            trust_role=rule.trust_role,
            reversibility=rule.reversibility,
            description=rule.explanation,
            rule_id=rule.id,
        )
        capabilities.append(cap)

    return capabilities


def _capability_name(func_name: str, rule: CapabilityRule) -> str:
    """Derive a human-readable capability name from the function name and rule."""
    # Use the primary tag label if available
    if rule.produced_tags and rule.produced_tags[0] != CapabilityTag.UNKNOWN:
        tag_label = str(rule.produced_tags[0]).replace("_", " ").title()
        return f"{func_name} [{tag_label}]"
    return f"{func_name} [Unknown]"


# ---------------------------------------------------------------------------
# Repository-level classification
# ---------------------------------------------------------------------------


def classify_capabilities(
    static_result: StaticAnalysisResult,
) -> tuple[list[Capability], CapabilityStatistics]:
    """Classify capabilities from a Phase 3 :class:`StaticAnalysisResult`.

    Args:
        static_result: The complete Phase 3 static analysis output.

    Returns:
        A tuple of ``(capabilities, statistics)``.
    """
    tool_candidate_names: frozenset[str] = frozenset(
        tc.qualified_name for tc in static_result.tool_candidates
    )

    all_capabilities: list[Capability] = []

    for module in static_result.modules:
        if module.parse_status != "ok":
            continue

        # Collect all functions: top-level + class methods
        functions: list[PythonFunction] = list(module.functions)
        for cls in module.classes:
            functions.extend(cls.methods)

        for func in functions:
            is_tool = func.qualified_name in tool_candidate_names
            caps = _classify_function(func, module, is_tool)
            all_capabilities.extend(caps)

    # Deduplicate: same (symbol, rule_id) pair — keep highest-confidence one
    deduped = _deduplicate(all_capabilities)

    statistics = _compute_statistics(deduped)
    return deduped, statistics


def _deduplicate(caps: list[Capability]) -> list[Capability]:
    """Remove duplicate (source_symbol, rule_id) capability pairs.

    When duplicates exist, keep the one with the highest confidence.
    """
    _conf_rank = {"high": 2, "medium": 1, "low": 0}
    seen: dict[tuple[str, str | None], Capability] = {}
    for cap in caps:
        key = (cap.source_symbol, cap.rule_id)
        existing = seen.get(key)
        if existing is None or _conf_rank.get(cap.confidence, 0) > _conf_rank.get(
            existing.confidence, 0
        ):
            seen[key] = cap
    return list(seen.values())


def _compute_statistics(caps: list[Capability]) -> CapabilityStatistics:
    """Compute aggregate statistics from a list of capabilities."""
    by_tag: dict[str, int] = defaultdict(int)
    by_side_effect: dict[str, int] = defaultdict(int)
    by_trust_role: dict[str, int] = defaultdict(int)

    for cap in caps:
        for tag in cap.tags:
            by_tag[str(tag)] += 1
        by_side_effect[str(cap.side_effect)] += 1
        by_trust_role[str(cap.trust_role)] += 1

    return CapabilityStatistics(
        total_capabilities=len(caps),
        by_tag=dict(by_tag),
        by_side_effect=dict(by_side_effect),
        by_trust_role=dict(by_trust_role),
    )
