"""
``viveka init`` — initialise VIVEKA in a project directory.

Creates:
  <cwd>/.viveka/config.yaml
  <cwd>/.viveka/properties/
  <cwd>/.viveka/.gitignore
  ~/.viveka/                    (user state directory)

The command is idempotent: running it twice produces a warning but does not
overwrite an existing config.yaml.

Nothing in the project directory is modified except the .viveka/ subtree.
No secrets are read.  No network calls are made.
"""

from __future__ import annotations

from pathlib import Path

import typer

from viveka.core.config import write_default_config
from viveka.core.paths import (
    project_config_path,
    project_dir,
    project_gitignore_path,
    project_properties_dir,
    user_state_dir,
)
from viveka.reporting.console import BRAND_HEADER, OK, WARN, console

# Content written to .viveka/.gitignore — keeps runtime artifacts out of git
# while still allowing config.yaml and properties/ to be committed.
_DOT_VIVEKA_GITIGNORE = """\
# VIVEKA runtime artifacts — do not commit (private-by-default)
*.db
*.db-shm
*.db-wal
traces/
runs/
.cache/
worlds/
reductions/
evaluations/
diagnoses/
regressions/
"""


def init_command(
    path: Path = typer.Argument(
        default=None,
        help="Project root directory (defaults to current working directory).",
        exists=False,  # allow missing so we can give a better error
        file_okay=False,
    ),
) -> None:
    """Initialise VIVEKA in a project directory."""
    root = (path or Path.cwd()).resolve()

    if not root.exists():
        console.print(f"[error]Directory not found:[/] {root}")
        raise typer.Exit(code=2)

    console.print(BRAND_HEADER)
    console.print()

    already_exists = project_config_path(root).exists()
    if already_exists:
        console.print(f"  {WARN} Project already initialised at [path]{root / '.viveka'}[/]")
        console.print(
            "  [muted]config.yaml was not overwritten. "
            "Edit it directly or delete .viveka/ to reinitialise.[/]"
        )
        console.print()
    else:
        # Create project state directories
        project_dir(root).mkdir(parents=True, exist_ok=True)
        project_properties_dir(root).mkdir(parents=True, exist_ok=True)

        # Write default config
        write_default_config(project_config_path(root))

        # Write .viveka/.gitignore
        project_gitignore_path(root).write_text(_DOT_VIVEKA_GITIGNORE, encoding="utf-8")

    # Always ensure user state directory exists (idempotent)
    user_dir = user_state_dir()

    # Report
    console.print("  [heading]Created:[/]")
    console.print(f"    {OK} [path].viveka/config.yaml[/]" if not already_exists else "")
    if not already_exists:
        console.print(f"    {OK} [path].viveka/properties/[/]")
    console.print()
    console.print("  [heading]Local state:[/]")
    console.print(f"    {OK} [path]{user_dir}/[/]")
    console.print()
    console.print("  [heading]Mode:[/]")
    console.print("    deterministic")
    console.print()
    console.print("  [muted]Next step:[/]")
    console.print("    viveka inspect .")
    console.print()
    raise typer.Exit()
