"""
Rich console helpers and VIVEKA visual theme.

All CLI commands import from here instead of constructing their own Console
instances, ensuring consistent styling across the entire tool.
"""

from __future__ import annotations

import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.theme import Theme

# ---------------------------------------------------------------------------
# VIVEKA colour palette
# ---------------------------------------------------------------------------
# Design intent: calm, professional, readable in both light and dark terminals.
# Avoid garish colours.  Use bold/dim for hierarchy rather than rainbow text.

_VIVEKA_THEME = Theme(
    {
        # Status indicators
        "ok": "bold green",
        "warn": "bold yellow",
        "error": "bold red",
        "info": "dim",
        # Domain concepts
        "property": "bold cyan",
        "capability": "cyan",
        "counterexample": "bold red",
        "regression": "magenta",
        "trial": "blue",
        # Structural
        "heading": "bold white",
        "muted": "dim white",
        "code": "bold",
        "path": "underline white",
        # Brand
        "brand": "bold white",
        "brand.sub": "dim white",
    }
)

# Shared console — import this everywhere, do not create new Console() instances.
console = Console(theme=_VIVEKA_THEME)

# ---------------------------------------------------------------------------
# Brand header
# ---------------------------------------------------------------------------

BRAND_HEADER = "[brand]VIVEKA[/] [brand.sub]· विवेक[/]"


def print_brand() -> None:
    """Print the VIVEKA brand header line."""
    console.print(BRAND_HEADER)


def print_separator() -> None:
    """Print a dim horizontal rule."""
    console.print("[muted]" + "─" * 60 + "[/]")


# ---------------------------------------------------------------------------
# Status symbols
# ---------------------------------------------------------------------------

OK = "[ok]✓[/]"
WARN = "[warn]![/]"
ERR = "[error]✗[/]"
INFO = "[info]·[/]"


def ok(msg: str) -> str:
    """Format a success status line."""
    return f"{OK} {msg}"


def warn(msg: str) -> str:
    """Format a warning status line."""
    return f"{WARN} {msg}"


def err(msg: str) -> str:
    """Format an error status line."""
    return f"{ERR} {msg}"


def hint(msg: str) -> str:
    """Format an actionable hint line."""
    return f"[muted]  → {msg}[/]"
