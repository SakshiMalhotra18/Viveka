"""
Deterministic structural reduction operators for Phase 6 Worlds.

Generates 1-step candidate World simplifications by removing single structural
elements (documents, conversation turns, memory entries, tool overrides, permissions,
environment configurations) while guaranteeing source World immutability.
"""

from __future__ import annotations

from viveka.core.ids import new_id
from viveka.reduction.models import ReductionCandidate
from viveka.reduction.vocabulary import ReductionOperator
from viveka.worlds.models import World


def generate_reduction_candidates(world: World) -> list[ReductionCandidate]:
    """Generate all 1-step structural candidate simplifications for a World.

    Operators are applied in deterministic priority order:
    1. REMOVE_RETRIEVAL_DOCUMENT
    2. REMOVE_CONVERSATION_TURN
    3. REMOVE_MEMORY_ENTRY
    4. REMOVE_TOOL_CONFIG
    5. REMOVE_USER_PERMISSION
    6. REMOVE_ENV_CONFIG

    Guarantees the input world is never mutated in-place.
    """
    candidates: list[ReductionCandidate] = []
    cand_counter = 1

    # 1. REMOVE_RETRIEVAL_DOCUMENT
    for i, doc in enumerate(world.retrieval.documents):
        cloned_world = world.model_copy(deep=True)
        cloned_world.id = new_id("VWORLD")
        cloned_world.retrieval.documents.pop(i)

        item_key = f"document:{doc.id}"
        candidates.append(
            ReductionCandidate(
                candidate_id=f"CAND-{cand_counter}",
                parent_world_id=world.id,
                operator=ReductionOperator.REMOVE_RETRIEVAL_DOCUMENT,
                target_item_key=item_key,
                world=cloned_world,
            )
        )
        cand_counter += 1

    # 2. REMOVE_CONVERSATION_TURN
    for i, turn in enumerate(world.state.conversation_history):
        cloned_world = world.model_copy(deep=True)
        cloned_world.id = new_id("VWORLD")
        cloned_world.state.conversation_history.pop(i)

        item_key = f"turn:{i}:{turn.role}"
        candidates.append(
            ReductionCandidate(
                candidate_id=f"CAND-{cand_counter}",
                parent_world_id=world.id,
                operator=ReductionOperator.REMOVE_CONVERSATION_TURN,
                target_item_key=item_key,
                world=cloned_world,
            )
        )
        cand_counter += 1

    # 3. REMOVE_MEMORY_ENTRY
    for key in sorted(world.state.memory.keys()):
        cloned_world = world.model_copy(deep=True)
        cloned_world.id = new_id("VWORLD")
        del cloned_world.state.memory[key]

        item_key = f"memory:{key}"
        candidates.append(
            ReductionCandidate(
                candidate_id=f"CAND-{cand_counter}",
                parent_world_id=world.id,
                operator=ReductionOperator.REMOVE_MEMORY_ENTRY,
                target_item_key=item_key,
                world=cloned_world,
            )
        )
        cand_counter += 1

    # 4. REMOVE_TOOL_CONFIG
    for tool_name in sorted(world.tools.keys()):
        cloned_world = world.model_copy(deep=True)
        cloned_world.id = new_id("VWORLD")
        del cloned_world.tools[tool_name]

        item_key = f"tool:{tool_name}"
        candidates.append(
            ReductionCandidate(
                candidate_id=f"CAND-{cand_counter}",
                parent_world_id=world.id,
                operator=ReductionOperator.REMOVE_TOOL_CONFIG,
                target_item_key=item_key,
                world=cloned_world,
            )
        )
        cand_counter += 1

    # 5. REMOVE_USER_PERMISSION (user.permissions or authorization.user_permissions)
    all_perms = set(world.user.permissions) | set(world.authorization.user_permissions)
    for perm in sorted(all_perms):
        cloned_world = world.model_copy(deep=True)
        cloned_world.id = new_id("VWORLD")
        if perm in cloned_world.user.permissions:
            cloned_world.user.permissions.remove(perm)
        if perm in cloned_world.authorization.user_permissions:
            cloned_world.authorization.user_permissions.remove(perm)

        item_key = f"permission:{perm}"
        candidates.append(
            ReductionCandidate(
                candidate_id=f"CAND-{cand_counter}",
                parent_world_id=world.id,
                operator=ReductionOperator.REMOVE_USER_PERMISSION,
                target_item_key=item_key,
                world=cloned_world,
            )
        )
        cand_counter += 1

    # 6. REMOVE_ENV_CONFIG
    for cfg_key in sorted(world.environment.available_configs.keys()):
        cloned_world = world.model_copy(deep=True)
        cloned_world.id = new_id("VWORLD")
        del cloned_world.environment.available_configs[cfg_key]

        item_key = f"env_config:{cfg_key}"
        candidates.append(
            ReductionCandidate(
                candidate_id=f"CAND-{cand_counter}",
                parent_world_id=world.id,
                operator=ReductionOperator.REMOVE_ENV_CONFIG,
                target_item_key=item_key,
                world=cloned_world,
            )
        )
        cand_counter += 1

    return candidates
