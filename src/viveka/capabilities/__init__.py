"""
VIVEKA Phase 4 — Capability Model, Semantic Classification, and Trust Boundaries.

Public API:
  - :func:`classify_capabilities` — classify Phase 3 output into capabilities.
  - :func:`build_capability_graph` — build a static capability graph.
  - :func:`infer_trust_boundaries` — infer trust boundaries from capabilities.
  - :class:`CapabilityAnalysisResult` — top-level Phase 4 result model.
"""

from __future__ import annotations

from viveka.capabilities.boundaries import infer_trust_boundaries
from viveka.capabilities.classifier import classify_capabilities
from viveka.capabilities.graph import build_capability_graph
from viveka.capabilities.models import (
    Capability,
    CapabilityAnalysisResult,
    CapabilityEvidence,
    CapabilityGraph,
    CapabilityStatistics,
    GraphEdge,
    GraphNode,
    TrustBoundary,
)
from viveka.capabilities.vocabulary import (
    CapabilityTag,
    Externality,
    Reversibility,
    SideEffect,
    TrustRole,
)

__all__ = [
    "Capability",
    "CapabilityAnalysisResult",
    "CapabilityEvidence",
    "CapabilityGraph",
    "CapabilityStatistics",
    "CapabilityTag",
    "Externality",
    "GraphEdge",
    "GraphNode",
    "Reversibility",
    "SideEffect",
    "TrustBoundary",
    "TrustRole",
    "build_capability_graph",
    "classify_capabilities",
    "infer_trust_boundaries",
]
