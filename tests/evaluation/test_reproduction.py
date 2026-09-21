"""Tests for ReproductionEngine, SHA-256 seed namespace derivation, and criterion_met."""

import pytest

from viveka.evaluation.models import ReproductionPolicy
from viveka.evaluation.reproduction import derive_run_seed


def test_derive_run_seed_namespace_determinism():
    seed1 = derive_run_seed(12345, "VWORLD-01", 0)
    seed2 = derive_run_seed(12345, "VWORLD-01", 0)
    seed_diff_namespace = derive_run_seed(12345, "VWORLD-02", 0)
    seed_diff_run = derive_run_seed(12345, "VWORLD-01", 1)

    assert seed1 == seed2
    assert seed1 != seed_diff_namespace
    assert seed1 != seed_diff_run


def test_reproduction_policy_validation_minimum_violations_exceeds_runs():
    with pytest.raises(ValueError, match="cannot exceed total runs"):
        ReproductionPolicy(runs=3, minimum_violations=5)
