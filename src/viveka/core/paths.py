"""
Canonical path helpers for VIVEKA.

Two-level state model (ADR-0003):

  Project state  →  <repo>/.viveka/
      Version-controlled.
      Contains: config.yaml, properties/, .gitignore
      Does NOT contain: database, traces, secrets.

  User state     →  ~/.viveka/
      Never committed.
      Contains: viveka.db, traces/, runs/, cached embeddings.

All modules that need a path must call these helpers — never construct
paths manually with os.path or string concatenation scattered through code.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# User (machine-local) state
# ---------------------------------------------------------------------------


def user_state_dir() -> Path:
    """Return ``~/.viveka/``, creating it if necessary."""
    path = Path.home() / ".viveka"
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_db_path() -> Path:
    """Return the canonical SQLite database path: ``~/.viveka/viveka.db``."""
    return user_state_dir() / "viveka.db"


# ---------------------------------------------------------------------------
# Project state (relative to a project root)
# ---------------------------------------------------------------------------


def project_dir(root: Path) -> Path:
    """Return ``<root>/.viveka/``."""
    return root / ".viveka"


def project_config_path(root: Path) -> Path:
    """Return ``<root>/.viveka/config.yaml``."""
    return project_dir(root) / "config.yaml"


def project_properties_dir(root: Path) -> Path:
    """Return ``<root>/.viveka/properties/``."""
    return project_dir(root) / "properties"


def project_gitignore_path(root: Path) -> Path:
    """Return ``<root>/.viveka/.gitignore``."""
    return project_dir(root) / ".gitignore"


# ---------------------------------------------------------------------------
# Safety helpers
# ---------------------------------------------------------------------------


def is_inside(path: Path, root: Path) -> bool:
    """Return True if *path* is inside *root* (resolves symlinks before check)."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
