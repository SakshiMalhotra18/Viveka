"""
``viveka version`` — print VIVEKA and Python versions.
"""

from __future__ import annotations

import platform
import sys

import typer

from viveka import __version__
from viveka.reporting.console import console


def version_command() -> None:
    """Show the installed VIVEKA version and Python version."""
    console.print(f"[brand]VIVEKA[/] [heading]{__version__}[/]")
    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    console.print(f"[muted]Python {py} · {platform.system()} {platform.machine()}[/]")
    raise typer.Exit()
