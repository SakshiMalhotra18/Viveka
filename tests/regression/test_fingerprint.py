"""Unit tests for regression fingerprinting."""

from viveka.evaluation.models import ReproductionPolicy
from viveka.properties.models import FlowForbiddenOracle, Property
from viveka.properties.vocabulary import PropertyStatus
from viveka.regression.fingerprint import compute_regression_fingerprint
from viveka.worlds.generate import WorldGenerator


def make_test_world():
    prop = Property(
        id="VPROP-01",
        stable_key="src/search.py::knowledge_search->src/refund.py::refund_create",
        name="test",
        description="test",
        status=PropertyStatus.APPROVED,
        oracle=FlowForbiddenOracle(
            evaluator_kind="flow_forbidden",
            untrusted_source_key="src/search.py::knowledge_search",
            forbidden_sink_key="src/refund.py::refund_create",
        ),
    )
    gen = WorldGenerator(seed=12345)
    return gen.generate_worlds([prop], max_worlds_per_property=1)[0]


def test_fingerprint_determinism() -> None:
    world = make_test_world()
    policy = ReproductionPolicy(runs=5, minimum_violations=3)

    fp1 = compute_regression_fingerprint("key1", 1, world, policy)
    fp2 = compute_regression_fingerprint("key1", 1, world, policy)
    assert fp1 == fp2
    assert len(fp1) == 64


def test_fingerprint_sensitivity() -> None:
    world = make_test_world()
    policy1 = ReproductionPolicy(runs=5, minimum_violations=3)
    policy2 = ReproductionPolicy(runs=10, minimum_violations=5)

    fp_base = compute_regression_fingerprint(
        "key1", 1, world, policy1, master_seed=12345, seed_namespace="ns1"
    )
    fp_diff_key = compute_regression_fingerprint(
        "key2", 1, world, policy1, master_seed=12345, seed_namespace="ns1"
    )
    fp_diff_rev = compute_regression_fingerprint(
        "key1", 2, world, policy1, master_seed=12345, seed_namespace="ns1"
    )
    fp_diff_pol = compute_regression_fingerprint(
        "key1", 1, world, policy2, master_seed=12345, seed_namespace="ns1"
    )
    fp_diff_seed = compute_regression_fingerprint(
        "key1", 1, world, policy1, master_seed=99999, seed_namespace="ns1"
    )
    fp_diff_ns = compute_regression_fingerprint(
        "key1", 1, world, policy1, master_seed=12345, seed_namespace="ns2"
    )
    fp_none_world = compute_regression_fingerprint(
        "key1", 1, None, policy1, master_seed=12345, seed_namespace="ns1"
    )

    assert fp_base != fp_diff_key
    assert fp_base != fp_diff_rev
    assert fp_base != fp_diff_pol
    assert fp_base != fp_diff_seed
    assert fp_base != fp_diff_ns
    assert fp_base != fp_none_world
