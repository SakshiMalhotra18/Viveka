"""
Regression fingerprint computation for VIVEKA Phase 10.

Produces a deterministic SHA-256 fingerprint used to deduplicate
BehavioralRegression artifacts with equivalent behavioral content.

Fingerprint inputs:
  - property_stable_key
  - property_revision
  - world_behavioral_fingerprint (from Phase 9 compute_world_fingerprint)
  - policy_runs
  - policy_minimum_violations

Not included: IDs, timestamps, seeds, target metadata.
"""

from __future__ import annotations

import hashlib
import json

from viveka.evaluation.models import ReproductionPolicy
from viveka.reduction.fingerprint import compute_world_fingerprint
from viveka.worlds.models import World


def compute_regression_fingerprint(
    property_stable_key: str,
    property_revision: int,
    final_world: World | None,
    policy: ReproductionPolicy,
    master_seed: int = 12345,
    seed_namespace: str = "",
) -> str:
    """Compute a deterministic SHA-256 regression fingerprint.

    Used to detect duplicate BehavioralRegression artifacts.
    Filenames are always derived from validated VREG IDs, not from this fingerprint.

    Args:
        property_stable_key: Stable property key.
        property_revision: Property revision number.
        final_world: Final World model (reduced or original). None yields empty string.
        policy: Reproduction policy.
        master_seed: Master random seed for stochastic derivation.
        seed_namespace: Stochastic seed namespace string.

    Returns:
        Lowercase SHA-256 hex digest string.
    """
    world_fp = compute_world_fingerprint(final_world) if final_world is not None else ""

    canonical = {
        "master_seed": master_seed,
        "policy_minimum_violations": policy.minimum_violations,
        "policy_runs": policy.runs,
        "property_revision": property_revision,
        "property_stable_key": property_stable_key,
        "seed_namespace": seed_namespace,
        "world_behavioral_fingerprint": world_fp,
    }
    raw = json.dumps(canonical, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
