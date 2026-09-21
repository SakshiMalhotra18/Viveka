"""Unit tests for DiagnosisStore."""

from pathlib import Path

from viveka.diagnosis.models import ContributingFactor, Diagnosis, DiagnosisEvidence
from viveka.diagnosis.store import DiagnosisStore
from viveka.runtime.vocabulary import RawEventType


def test_diagnosis_store_save_load_clear(tmp_path: Path) -> None:
    store = DiagnosisStore(tmp_path)
    diag = Diagnosis(
        diag_id="VDIAG-01JEXAMPLEDIAGNOSIS000001",
        reduction_id="VRED-01JEXAMPLEREDUCTION00001",
        property_id="VPROP-01JEXAMPLEPROPERTY00001",
        property_stable_key="flow:test",
        property_revision=1,
        world_id="VWORLD-01JEXAMPLEWORLD000001",
        original_world_id="VWORLD-01JEXAMPLEWORLD000001",
        expected_behavior="Expected nothing bad",
        observed_behavior="Observed violation",
        evidence=[
            DiagnosisEvidence(
                event_id="VEVT-1",
                sequence=1,
                event_type=RawEventType.TOOL_CALL,
                description="Test event",
            )
        ],
        contributing_factors=[
            ContributingFactor(
                factor_type="test_factor",
                label="Test factor label",
                description="Test description",
                evidence_event_ids=["VEVT-1"],
            )
        ],
        reproduction_summary="3 / 5 violations",
        limitations=["Limitation 1"],
    )

    saved_path = store.save(diag)
    assert saved_path.is_file()
    assert saved_path.name == f"{diag.diag_id}.yaml"

    loaded = store.load(diag.diag_id)
    assert loaded is not None
    assert loaded.diag_id == diag.diag_id
    assert loaded.property_stable_key == "flow:test"
    assert len(loaded.evidence) == 1
    assert loaded.evidence[0].event_id == "VEVT-1"

    # load_for_reduction
    loaded_for_red = store.load_for_reduction("VRED-01JEXAMPLEREDUCTION00001")
    assert loaded_for_red is not None
    assert loaded_for_red.diag_id == diag.diag_id

    # load_all
    all_diags = store.load_all()
    assert len(all_diags) == 1

    # clear
    cleared = store.clear()
    assert cleared == 1
    assert store.load_all() == []
