"""
Stable lexicographically sortable ID generation for VIVEKA domain objects.

Format:  <PREFIX>-<ULID>
Example: VCEX-01JY8M7KFQZRVF2BNXD3TYA9WG

The ULID component is:
  - 26 characters
  - monotonically sortable by creation time
  - URL-safe (uppercase Crockford Base32)
  - collision-resistant

Short display IDs (last 8 chars of the ULID) are used in CLI output only.
The full ID is always stored in the database and configuration files.

Registered prefixes (extend as new domain objects are added):
  VPROJ   Project
  VTGT    Target
  VCAP    Capability
  VPROP   Property
  VRUN    Run
  VWORLD  World
  VTRIAL  Trial
  VCEX    Counterexample
  VREG    Regression
  VDIAG   Diagnosis
  VMUT    Mutation
"""

from __future__ import annotations

from ulid import ULID

# Registered prefix registry — documents all domain ID types.
KNOWN_PREFIXES: frozenset[str] = frozenset(
    {
        "VPROJ",
        "VTGT",
        "VCAP",
        "VPROP",
        "VRUN",
        "VWORLD",
        "VTRIAL",
        "VCEX",
        "VREG",
        "VDIAG",
        "VMUT",
        "VTRC",
        "VEVAL",
        "VRED",
    }
)


def new_id(prefix: str) -> str:
    """Generate a new unique ID for the given domain prefix.

    Args:
        prefix: One of the registered VIVEKA prefixes (e.g. ``"VCEX"``).

    Returns:
        A string of the form ``"VCEX-01JY8M7KFQZRVF2BNXD3TYA9WG"``.
    """
    return f"{prefix}-{ULID()!s}"


def short_display(full_id: str) -> str:
    """Return a short human-readable representation for CLI display.

    Example: ``"VCEX-01JY8M7KFQZRVF2BNXD3TYA9WG"`` → ``"VCEX-…A9WG"``

    The full ID is always used for storage and programmatic references.
    This is purely cosmetic.
    """
    parts = full_id.split("-", 1)
    if len(parts) != 2:
        return full_id
    prefix, ulid_part = parts
    return f"{prefix}-…{ulid_part[-4:]}"
