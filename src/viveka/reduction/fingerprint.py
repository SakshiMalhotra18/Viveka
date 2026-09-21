"""
Deterministic behavioral fingerprint for Phase 6 Worlds.

Produces a canonical SHA-256 hash representation of a World's target-visible
behavioral properties, explicitly excluding IDs, timestamps, random seeds,
and provenance metadata.

Used by the reduction engine to detect and suppress duplicate candidates.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from viveka.worlds.models import World


def compute_world_fingerprint(world: World) -> str:
    """Compute a deterministic behavioral SHA-256 fingerprint for a World.

    Excludes: world.id, world.seed, world.created_at, world.mutations, document.id.
    Includes: user, input, retrieval, tools, environment, state, authorization.
    """
    canonical_data: dict[str, Any] = {
        "user": {
            "role": world.user.role,
            "permissions": sorted(world.user.permissions),
        },
        "input": {
            "message": world.input.message,
        },
        "retrieval": [
            {
                "trust": doc.trust.value,
                "content": doc.content,
                "metadata": sorted(doc.metadata.items()),
            }
            for doc in sorted(world.retrieval.documents, key=lambda d: (d.trust.value, d.content))
        ],
        "tools": [
            (
                name,
                cfg.behavior.value,
                cfg.response,
                cfg.error_message,
                cfg.latency_ms,
            )
            for name, cfg in sorted(world.tools.items())
        ],
        "environment": {
            "network_available": world.environment.network_available,
            "latency_ms": world.environment.latency_ms,
            "clock_offset_seconds": world.environment.clock_offset_seconds,
            "available_configs": sorted(world.environment.available_configs.items()),
        },
        "state": {
            "conversation_history": [
                {"role": turn.role, "content": turn.content}
                for turn in world.state.conversation_history
            ],
            "memory": sorted(world.state.memory.items()),
        },
        "authorization": {
            "user_permissions": sorted(world.authorization.user_permissions),
            "approval_granted": world.authorization.approval_granted,
            "approval_revoked": world.authorization.approval_revoked,
            "spending_threshold": world.authorization.spending_threshold,
        },
    }

    raw_json = json.dumps(canonical_data, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
