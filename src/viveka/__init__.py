"""
VIVEKA · विवेक — Discernment
Property-based verification engine for AI agents.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def get_version() -> str:
    """Return the installed package version from distribution metadata.

    Falls back to "0.0.0+unknown" when the package is not formally installed
    (e.g. during editable development without ``pip install -e .``).
    """
    try:
        return version("viveka-engine")
    except PackageNotFoundError:
        return "0.0.0+unknown"


__version__ = get_version()
