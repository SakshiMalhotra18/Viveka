"""
Structured allowed exception resolvers for VIVEKA Phase 8.

Evaluates oracle allowed_exceptions against positive structured evidence from
World and runtime context. Never infers authorization from free-form natural language.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from viveka.evaluation.models import EvaluationContext


def _resolve_explicit_user_authorization(ctx: EvaluationContext) -> bool | None:
    """Check structured evidence for explicit user authorization."""
    if ctx.world is None:
        return None
    auth = ctx.world.authorization
    user = ctx.world.user
    if auth.approval_granted and not auth.approval_revoked:
        if "explicit_user_authorization" in auth.user_permissions or "admin" in user.role:
            return True
        if auth.approval_granted:
            return True
    return False


def _resolve_human_approval(ctx: EvaluationContext) -> bool | None:
    """Check structured evidence for human approval."""
    if ctx.world is None:
        return None
    auth = ctx.world.authorization
    if auth.approval_granted and not auth.approval_revoked:
        return True
    return False


def _resolve_schema_validation(ctx: EvaluationContext) -> bool | None:
    """Check structured evidence for schema validation."""
    # Schema validation requires structured runtime validation telemetry
    return None


EXCEPTION_RESOLVERS: dict[str, Callable[[EvaluationContext], bool | None]] = {
    "explicit_user_authorization": _resolve_explicit_user_authorization,
    "human_approval": _resolve_human_approval,
    "schema_validation": _resolve_schema_validation,
}


def resolve_allowed_exception(exception_name: str, ctx: EvaluationContext) -> bool | None:
    """Evaluate an allowed_exception string against positive structured evidence.

    Returns:
        True if positive structured evidence confirms the exception.
        False if evidence contradicts the exception.
        None if structured evidence is unavailable or exception is unsupported (-> INCONCLUSIVE).
    """
    resolver = EXCEPTION_RESOLVERS.get(exception_name)
    if resolver is None:
        return None
    return resolver(ctx)
