"""
Tests for Phase 9 World behavioral fingerprint calculation and duplicate detection.
"""

from __future__ import annotations

from viveka.reduction.fingerprint import compute_world_fingerprint
from viveka.worlds.models import MutationRecord, World, WorldDocument


def test_fingerprint_excludes_ids_timestamps_seeds_mutations() -> None:
    w1 = World(
        id="VWORLD-11111111111111111111111111",
        property_id="VPROP-1",
        property_stable_key="p.key",
        seed=100,
    )
    w1.retrieval.documents.append(WorldDocument(id="doc-1", content="same content"))
    w1.mutations.append(
        MutationRecord(
            id="VMUT-1",
            operator="irrelevant_distractors",
            family="retrieval",
            target_slot="retrieval",
            description="added doc",
        )
    )

    w2 = World(
        id="VWORLD-22222222222222222222222222",
        property_id="VPROP-2",
        property_stable_key="p.key",
        seed=999,
    )
    w2.retrieval.documents.append(WorldDocument(id="doc-999", content="same content"))

    fp1 = compute_world_fingerprint(w1)
    fp2 = compute_world_fingerprint(w2)

    assert fp1 == fp2, "Fingerprints must match when target-visible behavior is identical."


def test_fingerprint_changes_on_behavioral_difference() -> None:
    w1 = World(id="VWORLD-1", property_id="VPROP-1", property_stable_key="p.key", seed=42)
    w1.state.memory["k"] = "v1"

    w2 = World(id="VWORLD-2", property_id="VPROP-1", property_stable_key="p.key", seed=42)
    w2.state.memory["k"] = "v2"

    assert compute_world_fingerprint(w1) != compute_world_fingerprint(w2)
