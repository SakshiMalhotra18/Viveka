"""Tests for viveka.properties.store — YAML persistence, lifecycle transitions, and candidate merging."""

from __future__ import annotations

from pathlib import Path

import pytest

from viveka.properties.models import (
    AppliesWhen,
    FlowForbiddenOracle,
    Property,
    PropertyEvidenceRef,
)
from viveka.properties.store import PropertyNotFoundError, PropertyStore
from viveka.properties.vocabulary import (
    PropertyEvidenceType,
    PropertySource,
    PropertyStatus,
)


def _make_prop(
    prop_id: str = "VPROP-01store",
    name: str = "store-test-prop",
    stable_key: str = "test:key:1",
    status: PropertyStatus = PropertyStatus.CANDIDATE,
) -> Property:
    return Property(
        id=prop_id,
        stable_key=stable_key,
        name=name,
        description="Store test property.",
        status=status,
        source=PropertySource.RULE_DERIVED,
        confidence="high",
        applies_when=AppliesWhen(source_capability_keys=["src/tools.py::search"]),
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="src/tools.py::search",
            forbidden_sink_key="src/tools.py::refund",
        ),
        evidence=[
            PropertyEvidenceRef(
                evidence_type=PropertyEvidenceType.CAPABILITY,
                source_id="src/tools.py::search",
                description="Search tool",
                file_path="src/tools.py",
                line=5,
            )
        ],
    )


class TestPropertyStore:
    def test_save_and_load_catalog(self, tmp_path: Path) -> None:
        store = PropertyStore(tmp_path)
        prop = _make_prop()
        file_path = store.save(prop)

        assert file_path.is_file()
        assert file_path.name == f"{prop.id}.yaml"

        catalog = store.load_catalog()
        assert len(catalog.properties) == 1
        loaded = catalog.properties[0]
        assert loaded.id == prop.id
        assert loaded.name == prop.name

    def test_approve_lifecycle_with_revision(self, tmp_path: Path) -> None:
        store = PropertyStore(tmp_path)
        prop = _make_prop(status=PropertyStatus.CANDIDATE)
        assert prop.revision == 1
        store.save(prop)

        approved = store.approve(prop.id)
        assert approved.status == PropertyStatus.APPROVED
        assert approved.revision == 2
        assert len(approved.revision_history) == 1
        assert approved.revision_history[0].status == PropertyStatus.APPROVED
        assert approved.revision_history[0].timestamp.tzinfo is not None

        # Verify persisted on disk
        reloaded = store.get(prop.id)
        assert reloaded is not None
        assert reloaded.status == PropertyStatus.APPROVED
        assert reloaded.revision == 2

    def test_reject_lifecycle_with_revision(self, tmp_path: Path) -> None:
        store = PropertyStore(tmp_path)
        prop = _make_prop(status=PropertyStatus.CANDIDATE)
        store.save(prop)

        rejected = store.reject(prop.id)
        assert rejected.status == PropertyStatus.REJECTED
        assert rejected.revision == 2
        assert len(rejected.revision_history) == 1

        reloaded = store.get(prop.id)
        assert reloaded is not None
        assert reloaded.status == PropertyStatus.REJECTED

    def test_approve_nonexistent_raises_error(self, tmp_path: Path) -> None:
        store = PropertyStore(tmp_path)
        with pytest.raises(PropertyNotFoundError):
            store.approve("VPROP-nonexistent")

    def test_merge_candidates_idempotency(self, tmp_path: Path) -> None:
        store = PropertyStore(tmp_path)
        p1 = _make_prop("VPROP-01", "prop-1", "stable:1")
        p2 = _make_prop("VPROP-02", "prop-2", "stable:2")

        # First merge: both are new
        new_props, kept = store.merge_candidates([p1, p2])
        assert len(new_props) == 2
        assert len(kept) == 0

        # Approve p1
        store.approve(p1.id)

        # Second merge with same candidates: none are new, p1 keeps APPROVED status and revision
        new_props2, kept2 = store.merge_candidates([p1, p2])
        assert len(new_props2) == 0
        assert len(kept2) == 2

        p1_reloaded = store.get(p1.id)
        assert p1_reloaded is not None
        assert p1_reloaded.status == PropertyStatus.APPROVED
        assert p1_reloaded.revision == 2
