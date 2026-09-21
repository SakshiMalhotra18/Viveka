"""
Shared pytest fixtures for VIVEKA tests.

Key fixtures:
  tmp_project   — a temporary directory pre-initialised as a VIVEKA project
  bare_project  — a temporary directory with NO .viveka/ (for testing missing-config paths)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from viveka.core.config import write_default_config
from viveka.core.paths import project_dir, project_gitignore_path, project_properties_dir


@pytest.fixture()
def tmp_project(tmp_path: Path) -> Path:
    """Return a temporary directory that has been initialised with a default config."""
    vd = project_dir(tmp_path)
    vd.mkdir(parents=True)
    project_properties_dir(tmp_path).mkdir()
    write_default_config(vd / "config.yaml")
    project_gitignore_path(tmp_path).write_text("*.db\n", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def bare_project(tmp_path: Path) -> Path:
    """Return a temporary directory with NO .viveka/ directory."""
    return tmp_path
