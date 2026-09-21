"""
Property inference engine for VIVEKA Phase 5.

Consumes Phase 4 CapabilityAnalysisResult and applies deterministic rules
under strict interaction evidence requirements to produce candidate properties.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from viveka.capabilities.models import Capability, CapabilityAnalysisResult
from viveka.capabilities.vocabulary import CapabilityTag
from viveka.core.ids import new_id
from viveka.properties.models import (
    AppliesWhen,
    FailureHandledOracle,
    FlowForbiddenOracle,
    Property,
    PropertyEvidenceRef,
)
from viveka.properties.rules import PROPERTY_RULES, PropertyInferenceRule
from viveka.properties.vocabulary import (
    InvariantType,
    PropertyEvidenceType,
    PropertySource,
    PropertyStatus,
)


def capability_key(cap: Capability) -> str:
    """Derive the path-qualified stable capability identity.

    Format: ``{project_relative_path}::{qualified_symbol}``
    Example: ``src/tools.py::refund_order``
    """
    return f"{cap.source_file}::{cap.source_symbol}"


def generate_stable_key(
    rule_id: str,
    invariant_type: str,
    source_cap_key: str,
    sink_cap_key: str | None = None,
) -> str:
    """Generate a deterministic, content-based stable key for a property.

    Derived directly from path-qualified stable capability keys.
    """
    if sink_cap_key is not None:
        return f"{rule_id}:{invariant_type}:{source_cap_key}->{sink_cap_key}".lower()
    return f"{rule_id}:{invariant_type}:{source_cap_key}".lower()


def _slugify(text: str) -> str:
    """Convert a name into a clean kebab-case slug."""
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text)


def _has_strong_interaction(
    analysis: CapabilityAnalysisResult,
    src_cap: Capability,
    sink_cap: Capability,
) -> tuple[bool, list[PropertyEvidenceRef]]:
    """Determine whether strong interaction evidence links src_cap and sink_cap.

    Co-location in the same module may corroborate an interaction, but will
    NOT independently trigger a cross-capability property. A confirmed graph
    path, shared reachable workflow context, or trust-boundary flow is strictly
    required.
    """
    evidence: list[PropertyEvidenceRef] = []
    src_sym = src_cap.source_symbol
    sink_sym = sink_cap.source_symbol

    # 1. Check direct edges in CapabilityGraph
    src_node_id = f"sym:{src_sym}"
    sink_node_id = f"sym:{sink_sym}"

    for edge in analysis.graph.edges:
        if (edge.source in (src_node_id, src_sym) and edge.target in (sink_node_id, sink_sym)) or (
            edge.source in (sink_node_id, sink_sym) and edge.target in (src_node_id, src_sym)
        ):
            evidence.append(
                PropertyEvidenceRef(
                    evidence_type=PropertyEvidenceType.GRAPH_PATH,
                    source_id=f"{edge.source}->{edge.target}",
                    description=f"Static capability graph edge: {edge.edge_type} ({edge.evidence})",
                    file_path=src_cap.source_file,
                    line=src_cap.source_line,
                )
            )
            return True, evidence

    # 2. Check workflow/entrypoint reachability (e.g. entrypoint reaches both or possible_interaction)
    # If both symbols are registered tools in the graph, check if an entrypoint interacts with both
    tool_nodes = {n.id: n for n in analysis.graph.nodes if n.node_type == "tool"}
    ep_nodes = {n.id: n for n in analysis.graph.nodes if n.node_type == "entrypoint"}

    if (src_node_id in tool_nodes or src_sym in tool_nodes) and (
        sink_node_id in tool_nodes or sink_sym in tool_nodes
    ):
        # Check if an entrypoint has interactions with both
        for ep_id in ep_nodes:
            has_src = any(
                e.source == ep_id and e.target in (src_node_id, src_sym)
                for e in analysis.graph.edges
            )
            has_sink = any(
                e.source == ep_id and e.target in (sink_node_id, sink_sym)
                for e in analysis.graph.edges
            )
            if has_src and has_sink:
                evidence.append(
                    PropertyEvidenceRef(
                        evidence_type=PropertyEvidenceType.GRAPH_PATH,
                        source_id=ep_id,
                        description=f"Shared workflow entrypoint reachability: {ep_id}",
                        file_path=src_cap.source_file,
                        line=None,
                    )
                )
                return True, evidence

    # 3. Check Trust Boundary flow (untrusted ingress -> agent:context -> privileged/external sink)
    ingress_boundaries = [
        tb
        for tb in analysis.trust_boundaries
        if tb.boundary_type == "untrusted_ingress" and tb.destination == "agent:context"
    ]
    sink_boundaries = [
        tb
        for tb in analysis.trust_boundaries
        if tb.boundary_type in ("privileged_sink", "external_sink") and tb.source == "agent:context"
    ]

    # If src_cap is linked to an untrusted ingress and sink_cap is linked to a sink boundary
    src_in_ingress = (
        any(
            src_sym in tb.evidence
            or any(src_sym in ev for ev in tb.evidence)
            or tb.source == f"sym:{src_sym}"
            or tb.source == src_sym
            for tb in ingress_boundaries
        )
        or src_cap.trust_role.value == "untrusted_ingress"
    )

    sink_in_sink = any(
        sink_sym in tb.evidence
        or any(sink_sym in ev for ev in tb.evidence)
        or tb.destination == f"sym:{sink_sym}"
        or tb.destination == sink_sym
        for tb in sink_boundaries
    ) or sink_cap.trust_role.value in ("privileged_sink", "external_sink")

    if ingress_boundaries and sink_boundaries and src_in_ingress and sink_in_sink:
        evidence.append(
            PropertyEvidenceRef(
                evidence_type=PropertyEvidenceType.TRUST_BOUNDARY,
                source_id=f"{ingress_boundaries[0].id}->{sink_boundaries[0].id}",
                description="Reachable path across verified untrusted ingress and privileged/external sink boundaries",
                file_path=src_cap.source_file,
                line=None,
            )
        )
        return True, evidence

    return False, []


def infer_candidate_properties(
    analysis: CapabilityAnalysisResult,
) -> list[Property]:
    """Infer candidate properties deterministically from CapabilityAnalysisResult.

    Upstream contract: Consumes the complete Phase 4 analysis result.
    """
    candidates: list[Property] = []

    # Identify agent-callable / exposed tools from graph nodes
    exposed_tool_symbols: set[str] = {
        n.label for n in analysis.graph.nodes if n.node_type == "tool"
    } | {n.id.replace("sym:", "") for n in analysis.graph.nodes if n.node_type == "tool"}

    # Index capabilities by tag
    caps_by_tag: dict[CapabilityTag, list[Capability]] = {}
    for cap in analysis.capabilities:
        for tag in cap.tags:
            caps_by_tag.setdefault(tag, []).append(cap)

    for rule in PROPERTY_RULES:
        # Rule: failure handling on exposed tools
        if rule.invariant_type == InvariantType.MUST_HANDLE_FAILURE:
            candidates.extend(
                _evaluate_failure_rule(rule, analysis.capabilities, exposed_tool_symbols)
            )
            continue

        # Pairwise flow rules
        matching_sources: list[Capability] = []
        for s_tag in rule.required_source_tags:
            matching_sources.extend(caps_by_tag.get(s_tag, []))
        unique_sources = {capability_key(c): c for c in matching_sources}

        matching_sinks: list[Capability] = []
        for d_tag in rule.required_sink_tags:
            matching_sinks.extend(caps_by_tag.get(d_tag, []))
        unique_sinks = {capability_key(c): c for c in matching_sinks}

        if not unique_sources or not unique_sinks:
            continue

        for src_key, src_cap in unique_sources.items():
            for sink_key, sink_cap in unique_sinks.items():
                # False-positive guard: source and sink cannot be identical symbol
                if src_cap.source_symbol == sink_cap.source_symbol:
                    continue

                # Strict interaction check: co-location alone is NOT sufficient
                has_interaction, interaction_ev = _has_strong_interaction(
                    analysis, src_cap, sink_cap
                )
                if not has_interaction:
                    continue

                prop = _build_flow_property(
                    rule, src_cap, sink_cap, src_key, sink_key, interaction_ev
                )
                candidates.append(prop)

    # Deduplicate candidates within this run by stable_key
    seen_keys: set[str] = set()
    deduped: list[Property] = []
    for c in candidates:
        if c.stable_key not in seen_keys:
            seen_keys.add(c.stable_key)
            deduped.append(c)

    return deduped


def _evaluate_failure_rule(
    rule: PropertyInferenceRule,
    capabilities: list[Capability],
    exposed_tool_symbols: set[str],
) -> list[Property]:
    """Evaluate PROP-RULE-FAIL-SILENT-001 strictly on exposed mutating tools."""
    props: list[Property] = []
    seen_keys: set[str] = set()

    for cap in capabilities:
        if cap.side_effect in rule.required_side_effects:
            # Enforce exposed tool restriction: internal helpers are omitted
            if rule.requires_exposed_tool and cap.source_symbol not in exposed_tool_symbols:
                continue

            cap_key = capability_key(cap)
            if cap_key in seen_keys:
                continue
            seen_keys.add(cap_key)

            short_sink = cap.source_symbol.split(".")[-1]
            prop_name = _slugify(rule.name_template.format(sink_name=short_sink))
            stable_key = generate_stable_key(
                rule_id=rule.id,
                invariant_type=rule.invariant_type.value,
                source_cap_key=cap_key,
            )

            evidence = [
                PropertyEvidenceRef(
                    evidence_type=PropertyEvidenceType.CAPABILITY,
                    source_id=cap_key,
                    description=f"Exposed mutating tool: {cap.source_symbol}",
                    file_path=cap.source_file,
                    line=cap.source_line,
                )
            ]

            prop = Property(
                id=new_id("VPROP"),
                stable_key=stable_key,
                name=prop_name,
                description=rule.description_template,
                status=PropertyStatus.CANDIDATE,
                source=PropertySource.RULE_DERIVED,
                confidence=rule.confidence,
                applies_when=AppliesWhen(
                    sink_capability_keys=[cap_key],
                    sink_symbols=[cap.source_symbol],
                ),
                oracle=FailureHandledOracle(
                    evaluator_kind="failure_handled",
                    target_action_key=cap_key,
                    must_not_represent_action_as_successful=True,
                ),
                evidence=evidence,
                rationale=rule.rationale_template.format(sink_name=cap.source_symbol),
                rule_id=rule.id,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            props.append(prop)

    return props


def _build_flow_property(
    rule: PropertyInferenceRule,
    src_cap: Capability,
    sink_cap: Capability,
    src_key: str,
    sink_key: str,
    interaction_evidence: list[PropertyEvidenceRef],
) -> Property:
    """Build a forbidden flow Property from an interacting capability pair."""
    short_sink = sink_cap.source_symbol.split(".")[-1]
    prop_name = _slugify(rule.name_template.format(sink_name=short_sink))

    stable_key = generate_stable_key(
        rule_id=rule.id,
        invariant_type=rule.invariant_type.value,
        source_cap_key=src_key,
        sink_cap_key=sink_key,
    )

    evidence = [
        PropertyEvidenceRef(
            evidence_type=PropertyEvidenceType.CAPABILITY,
            source_id=src_key,
            description=f"Untrusted ingress capability: {src_cap.source_symbol}",
            file_path=src_cap.source_file,
            line=src_cap.source_line,
        ),
        PropertyEvidenceRef(
            evidence_type=PropertyEvidenceType.CAPABILITY,
            source_id=sink_key,
            description=f"Sink capability: {sink_cap.source_symbol}",
            file_path=sink_cap.source_file,
            line=sink_cap.source_line,
        ),
        *interaction_evidence,
    ]

    return Property(
        id=new_id("VPROP"),
        stable_key=stable_key,
        name=prop_name,
        description=rule.description_template,
        status=PropertyStatus.CANDIDATE,
        source=PropertySource.RULE_DERIVED,
        confidence=rule.confidence,
        applies_when=AppliesWhen(
            source_capability_keys=[src_key],
            sink_capability_keys=[sink_key],
            source_symbols=[src_cap.source_symbol],
            sink_symbols=[sink_cap.source_symbol],
        ),
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key=src_key,
            forbidden_sink_key=sink_key,
            allowed_exceptions=list(rule.unless),
        ),
        evidence=evidence,
        rationale=rule.rationale_template.format(
            source_name=src_cap.source_symbol,
            sink_name=sink_cap.source_symbol,
        ),
        rule_id=rule.id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
