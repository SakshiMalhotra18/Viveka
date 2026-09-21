"""
Pydantic models for VIVEKA Phase 4 capability analysis.

These models represent:
  - Individual capabilities with evidence and semantic metadata.
  - A static capability graph (nodes + edges).
  - Trust boundary assertions derived from static evidence.
  - The aggregated CapabilityAnalysisResult.

All models are static-only.  No LLM inference.  No target code execution.
``static_only = True`` is a literal assertion on every TrustBoundary — it
signals to downstream consumers that these results come from structural
analysis, not dynamic observation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from viveka.capabilities.vocabulary import (
    CapabilityTag,
    Externality,
    Reversibility,
    SideEffect,
    TrustRole,
)

# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------


class CapabilityEvidence(BaseModel):
    """A single piece of static evidence supporting a capability assignment.

    Evidence items are collected by the classifier from AST structures
    (imports, calls, decorators, names) and referenced in the parent
    :class:`Capability`.
    """

    evidence_type: str = Field(
        description=(
            "Category of evidence: 'import', 'call', 'decorator', 'name_match', "
            "'parameter', 'docstring', 'rule'."
        )
    )
    value: str = Field(
        description="The concrete string that triggered this evidence (e.g. 'os.remove')."
    )
    file_path: str = Field(description="Project-relative path of the source file.")
    line: int = Field(ge=1, description="Line number of the evidence.")
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Relative weight of this evidence item (0.0-1.0).",
    )


# ---------------------------------------------------------------------------
# Capability
# ---------------------------------------------------------------------------


class Capability(BaseModel):
    """A single inferred capability of a target symbol.

    A capability is NOT a risk verdict — it describes what a symbol
    *appears capable of doing* based on static structural evidence.
    """

    id: str = Field(description="Unique VCAP-prefixed ULID identifier.")
    name: str = Field(description="Short human-readable capability name.")
    source_symbol: str = Field(
        description="Qualified name of the Python symbol this capability was inferred from."
    )
    source_file: str = Field(description="Project-relative path of the source file.")
    source_line: int = Field(ge=1, description="Line number of the symbol definition.")
    tags: list[CapabilityTag] = Field(
        default_factory=list,
        description="Semantic capability tags assigned by classification rules.",
    )
    confidence: str = Field(description="Confidence level: 'high', 'medium', or 'low'.")
    evidence: list[CapabilityEvidence] = Field(
        default_factory=list,
        description="Evidence items that support this capability.",
    )
    side_effect: SideEffect = Field(
        default=SideEffect.UNKNOWN,
        description="Mutation side-effect profile.",
    )
    externality: Externality = Field(
        default=Externality.UNKNOWN,
        description="Whether the capability reaches external systems.",
    )
    reversibility: Reversibility = Field(
        default=Reversibility.UNKNOWN,
        description="Static assessment of reversibility.",
    )
    trust_role: TrustRole = Field(
        default=TrustRole.UNKNOWN,
        description="Trust boundary role of this capability.",
    )
    description: str = Field(
        default="",
        description="Human-readable description of what was detected.",
    )
    rule_id: str | None = Field(
        default=None,
        description="ID of the CapabilityRule that produced this capability, if applicable.",
    )


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


class GraphNode(BaseModel):
    """A node in the static capability graph."""

    id: str = Field(description="Unique node identifier (e.g. qualified symbol name or VCAP id).")
    label: str = Field(description="Human-readable label.")
    node_type: str = Field(
        description=("Node category: 'entrypoint', 'symbol', 'tool', 'capability', 'module'.")
    )
    file_path: str | None = Field(default=None, description="Project-relative path, if applicable.")
    line: int | None = Field(default=None, description="Source line number, if applicable.")
    properties: dict[str, str] = Field(
        default_factory=dict,
        description="Additional string-valued properties for this node.",
    )


class GraphEdge(BaseModel):
    """A directed edge in the static capability graph."""

    source: str = Field(description="Source node ID.")
    target: str = Field(description="Target node ID.")
    edge_type: str = Field(
        description=(
            "Edge category: 'calls', 'references', 'exposes', 'has_capability', "
            "'possible_interaction', 'imports'."
        )
    )
    evidence: str = Field(
        default="",
        description="Short human-readable evidence string for this edge.",
    )
    confidence: str = Field(
        default="medium",
        description="Confidence in this edge: 'high', 'medium', or 'low'.",
    )


class CapabilityGraph(BaseModel):
    """Directed static capability graph of the inspected repository."""

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Trust Boundaries
# ---------------------------------------------------------------------------


class TrustBoundary(BaseModel):
    """A statically inferred trust boundary between two symbols or roles.

    Every TrustBoundary produced by VIVEKA carries ``static_only = True``
    to clearly signal that this is a structural inference, not runtime proof.
    """

    id: str = Field(description="Unique identifier for this boundary.")
    boundary_type: str = Field(
        description=(
            "Boundary category: 'untrusted_ingress', 'sensitive_source', "
            "'privileged_sink', 'external_sink'."
        )
    )
    source: str = Field(description="Qualified name of the source symbol / capability.")
    destination: str = Field(description="Qualified name of the destination symbol / capability.")
    confidence: str = Field(description="Confidence: 'high', 'medium', or 'low'.")
    evidence: list[str] = Field(
        default_factory=list,
        description="Short evidence strings supporting this boundary.",
    )
    static_only: bool = Field(
        default=True,
        description=(
            "Always True — boundary was inferred from static analysis only, "
            "never from dynamic observation."
        ),
    )


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


class CapabilityStatistics(BaseModel):
    """Aggregate counts from capability analysis."""

    total_capabilities: int = Field(ge=0, default=0)
    total_trust_boundaries: int = Field(ge=0, default=0)
    total_graph_nodes: int = Field(ge=0, default=0)
    total_graph_edges: int = Field(ge=0, default=0)
    by_tag: dict[str, int] = Field(
        default_factory=dict,
        description="Count of capabilities per CapabilityTag value.",
    )
    by_side_effect: dict[str, int] = Field(
        default_factory=dict,
        description="Count of capabilities per SideEffect value.",
    )
    by_trust_role: dict[str, int] = Field(
        default_factory=dict,
        description="Count of capabilities per TrustRole value.",
    )


# ---------------------------------------------------------------------------
# Top-level result
# ---------------------------------------------------------------------------


class CapabilityAnalysisResult(BaseModel):
    """Aggregated Phase 4 capability analysis result for an inspected repository."""

    capabilities: list[Capability] = Field(default_factory=list)
    trust_boundaries: list[TrustBoundary] = Field(default_factory=list)
    graph: CapabilityGraph = Field(default_factory=CapabilityGraph)
    statistics: CapabilityStatistics = Field(default_factory=CapabilityStatistics)
