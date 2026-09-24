"""
Static trust boundary inference for VIVEKA Phase 4.

Infers :class:`~viveka.capabilities.models.TrustBoundary` objects from the
classified capabilities list.  All boundaries are ``static_only = True``.

Four boundary types are inferred:
  untrusted_ingress
      A capability tagged as retrieval or untrusted_input feeds into the
      agent context.

  sensitive_source
      A capability tagged as sensitive_read, secret_access, or database_read
      is a source of privileged data.

  privileged_sink
      A capability tagged as financial_write, destructive_write,
      shell_execution, or code_execution is a privileged action sink.

  external_sink
      A capability tagged as communication, external_write, or network_write
      sends data outside the system boundary.

No LLMs, no network, no target code execution.
"""

from __future__ import annotations

from viveka.capabilities.models import Capability, TrustBoundary
from viveka.capabilities.vocabulary import CapabilityTag

# ---------------------------------------------------------------------------
# Tag sets that define each boundary type
# ---------------------------------------------------------------------------

_UNTRUSTED_INGRESS_TAGS: frozenset[CapabilityTag] = frozenset(
    {CapabilityTag.RETRIEVAL, CapabilityTag.UNTRUSTED_INPUT}
)

_SENSITIVE_SOURCE_TAGS: frozenset[CapabilityTag] = frozenset(
    {CapabilityTag.SENSITIVE_READ, CapabilityTag.SECRET_ACCESS, CapabilityTag.DATABASE_READ}
)

_PRIVILEGED_SINK_TAGS: frozenset[CapabilityTag] = frozenset(
    {
        CapabilityTag.FINANCIAL_WRITE,
        CapabilityTag.DESTRUCTIVE_WRITE,
        CapabilityTag.SHELL_EXECUTION,
        CapabilityTag.CODE_EXECUTION,
        CapabilityTag.DATABASE_WRITE,
    }
)

_EXTERNAL_SINK_TAGS: frozenset[CapabilityTag] = frozenset(
    {
        CapabilityTag.COMMUNICATION,
        CapabilityTag.EXTERNAL_WRITE,
        CapabilityTag.NETWORK_WRITE,
    }
)


# ---------------------------------------------------------------------------
# Boundary ID counter (simple sequential for determinism in tests)
# ---------------------------------------------------------------------------


def _boundary_id(index: int) -> str:
    return f"VBOUND-{index:04d}"


# ---------------------------------------------------------------------------
# Inference engine
# ---------------------------------------------------------------------------


def infer_trust_boundaries(
    capabilities: list[Capability],
) -> list[TrustBoundary]:
    """Infer trust boundaries from a list of capabilities.

    Args:
        capabilities: The Phase 4 capability list produced by the classifier.

    Returns:
        A list of :class:`TrustBoundary` objects (all ``static_only = True``).
    """
    boundaries: list[TrustBoundary] = []
    counter = 0

    for cap in capabilities:
        tag_set = frozenset(cap.tags)
        boundary_type: str | None = None

        if tag_set & _UNTRUSTED_INGRESS_TAGS:
            boundary_type = "untrusted_ingress"
        elif tag_set & _SENSITIVE_SOURCE_TAGS:
            boundary_type = "sensitive_source"
        elif tag_set & _PRIVILEGED_SINK_TAGS:
            boundary_type = "privileged_sink"
        elif tag_set & _EXTERNAL_SINK_TAGS:
            boundary_type = "external_sink"

        if boundary_type is None:
            continue

        evidence_items = [
            f"{e.evidence_type}:{e.value} @ {e.file_path}:{e.line}" for e in cap.evidence[:5]
        ]

        counter += 1
        boundary = TrustBoundary(
            id=_boundary_id(counter),
            boundary_type=boundary_type,
            source=_source_for(boundary_type, cap.source_symbol),
            destination=_destination_for(boundary_type, cap.source_symbol),
            confidence=cap.confidence,
            evidence=evidence_items,
            static_only=True,
        )
        boundaries.append(boundary)

    return boundaries


def _source_for(boundary_type: str, symbol: str) -> str:
    """Return the conceptual source of a trust boundary."""
    if boundary_type == "untrusted_ingress":
        return "external:untrusted_source"
    if boundary_type == "sensitive_source":
        return symbol
    if boundary_type in ("privileged_sink", "external_sink"):
        return "agent:context"
    return symbol


def _destination_for(boundary_type: str, symbol: str) -> str:
    """Return the conceptual destination of a trust boundary."""
    if boundary_type == "untrusted_ingress":
        return "agent:context"
    if boundary_type == "sensitive_source":
        return "agent:context"
    if boundary_type == "privileged_sink":
        return symbol
    if boundary_type == "external_sink":
        return symbol
    return symbol
