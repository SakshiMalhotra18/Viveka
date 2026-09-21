"""
VIVEKA Phase 5 — Property Engine, Candidate Suggestions, and Baseline Store.

Public API:
  - :class:`Property` — Core behavioral property model.
  - :class:`PropertyCatalog` — Collection of loaded properties.
  - :class:`PropertyStore` — File-based YAML persistence manager.
  - :func:`infer_candidate_properties` — Deterministic property inference.
  - :func:`generate_stable_key` — Deterministic stable key generator.
  - :func:`capability_key` — Path-qualified stable capability identity.
"""

from __future__ import annotations

from viveka.properties.engine import (
    capability_key,
    generate_stable_key,
    infer_candidate_properties,
)
from viveka.properties.models import (
    AppliesWhen,
    FailureHandledOracle,
    FlowForbiddenOracle,
    Property,
    PropertyCatalog,
    PropertyEvidenceRef,
    PropertyOracle,
    PropertyRevisionRecord,
)
from viveka.properties.rules import (
    PROPERTY_RULES,
    PROPERTY_RULES_BY_ID,
    PropertyInferenceRule,
)
from viveka.properties.store import (
    PropertyNotFoundError,
    PropertyStore,
)
from viveka.properties.vocabulary import (
    InvariantType,
    PropertyEvidenceType,
    PropertySource,
    PropertyStatus,
)

__all__ = [
    "PROPERTY_RULES",
    "PROPERTY_RULES_BY_ID",
    "AppliesWhen",
    "FailureHandledOracle",
    "FlowForbiddenOracle",
    "InvariantType",
    "Property",
    "PropertyCatalog",
    "PropertyEvidenceRef",
    "PropertyEvidenceType",
    "PropertyInferenceRule",
    "PropertyNotFoundError",
    "PropertyOracle",
    "PropertyRevisionRecord",
    "PropertySource",
    "PropertyStatus",
    "PropertyStore",
    "capability_key",
    "generate_stable_key",
    "infer_candidate_properties",
]
