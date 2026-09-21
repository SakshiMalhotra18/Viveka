"""
``viveka doctor`` — check environment readiness.

Checks:
  1.  Python version ≥ 3.12
  2.  VIVEKA version
  3.  Project configuration (.viveka/config.yaml)
  4.  User state directory writable (~/.viveka/)
  5.  SQLite writable (small probe write)
  6.  Reasoning mode configured
  7.  Ollama availability (informational; only required when mode=local)
  8.  Deterministic mode always available
  9.  Git availability

All checks produce ✓ / ! / ✗ symbols.
The exit code is 0 (Ready) if no critical check fails.
The exit code is 1 if any critical check fails.
Ollama being absent is never critical unless mode=local.
"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import typer

from viveka import __version__
from viveka.core.config import VivekaConfig, load_config
from viveka.core.errors import ConfigurationError
from viveka.core.paths import project_config_path, user_state_dir
from viveka.reporting.console import BRAND_HEADER, ERR, OK, WARN, console

# Minimum Python version required
_MIN_PYTHON = (3, 12)


def _check_python() -> tuple[bool, str]:
    vi = sys.version_info
    version_str = f"{vi.major}.{vi.minor}.{vi.micro}"
    ok = (vi.major, vi.minor) >= _MIN_PYTHON
    return ok, version_str


def _check_viveka() -> tuple[bool, str]:
    return True, __version__


def _check_project_config(root: Path) -> tuple[bool, str, VivekaConfig | None]:
    cfg_path = project_config_path(root)
    if not cfg_path.exists():
        return False, str(cfg_path), None
    try:
        cfg = load_config(cfg_path)
        return True, str(cfg_path), cfg
    except ConfigurationError as exc:
        return False, str(exc), None


def _check_user_state() -> tuple[bool, str]:
    try:
        d = user_state_dir()
        return True, str(d)
    except OSError as exc:
        return False, str(exc)


def _check_sqlite() -> tuple[bool, str]:
    try:
        user_dir = user_state_dir()
        with tempfile.NamedTemporaryFile(dir=user_dir, suffix=".probe.db", delete=True) as f:
            probe_path = f.name
        conn = sqlite3.connect(probe_path)
        conn.execute("CREATE TABLE _probe (id INTEGER PRIMARY KEY)")
        conn.close()
        Path(probe_path).unlink(missing_ok=True)
        return True, "SQLite writable"
    except Exception as exc:
        return False, str(exc)


def _check_ollama() -> tuple[bool, str]:
    """Attempt a TCP connection to the Ollama default port."""
    import socket

    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=1.5):
            return True, "Ollama detected at localhost:11434"
    except OSError:
        return False, "Ollama not detected (optional — needed for mode: local)"


def _check_git() -> tuple[bool, str]:
    git = shutil.which("git")
    if git is None:
        return False, "git not found in PATH (optional)"
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        version = result.stdout.strip()
        return True, version
    except Exception:
        return False, "git found but could not determine version"


def doctor_command(
    path: Path = typer.Argument(
        default=None,
        help="Project root directory (defaults to current working directory).",
        file_okay=False,
        exists=False,
    ),
) -> None:
    """Check environment readiness for VIVEKA."""
    root = (path or Path.cwd()).resolve()

    console.print(BRAND_HEADER)
    console.print()
    console.print("  [heading]VIVEKA Doctor[/]")
    console.print()

    critical_failures: list[str] = []

    def _row(symbol: str, label: str, detail: str = "") -> None:
        suffix = f"  [muted]{detail}[/]" if detail else ""
        console.print(f"  {symbol} {label}{suffix}")

    # 1. Python version
    py_ok, py_str = _check_python()
    if py_ok:
        _row(OK, f"Python {py_str}")
    else:
        _row(ERR, f"Python {py_str}", f"requires Python {_MIN_PYTHON[0]}.{_MIN_PYTHON[1]}+")
        critical_failures.append(f"Python {py_str} is below the required 3.12")

    # 2. VIVEKA version
    _, vv = _check_viveka()
    _row(OK, f"VIVEKA {vv}")

    # 3. Project config
    cfg_ok, cfg_detail, cfg = _check_project_config(root)
    if cfg_ok:
        _row(OK, "Project configuration")
    else:
        _row(ERR, "Project configuration not found")
        console.print(f"    [muted]{cfg_detail}[/]")
        console.print("    [muted]→ Run [code]viveka init[/] to create a project configuration.[/]")
        critical_failures.append("Missing project configuration")

    # 4. User state directory
    usr_ok, usr_detail = _check_user_state()
    if usr_ok:
        _row(OK, f"User state  [muted]{usr_detail}[/]")
    else:
        _row(ERR, "User state directory not writable", usr_detail)
        critical_failures.append("User state directory not writable")

    # 5. SQLite
    sq_ok, sq_detail = _check_sqlite()
    if sq_ok:
        _row(OK, "SQLite available")
    else:
        _row(ERR, "SQLite write probe failed", sq_detail)
        critical_failures.append("SQLite not writable")

    # 6. Reasoning mode
    if cfg:
        mode = cfg.reasoning.mode
        _row(OK, f"Reasoning mode: [code]{mode}[/]")
    else:
        _row(WARN, "Reasoning mode: unknown (no config)")

    # 7. Deterministic mode — always available (no external dependency)
    _row(OK, "Deterministic mode available")

    # 8. Ollama — informational; only critical if mode=local
    ol_ok, ol_detail = _check_ollama()
    requires_ollama = cfg is not None and cfg.reasoning.mode == "local"
    if ol_ok:
        _row(OK, "Ollama", ol_detail)
    elif requires_ollama:
        _row(ERR, "Ollama not detected", "required for reasoning.mode: local")
        critical_failures.append("Ollama not available (required for local mode)")
    else:
        _row(WARN, "Ollama not detected", "optional — needed for reasoning.mode: local")

    # 9. Git
    git_ok, git_detail = _check_git()
    if git_ok:
        _row(OK, f"Git  [muted]{git_detail}[/]")
    else:
        _row(WARN, "Git not found", git_detail)

    console.print()

    if critical_failures:
        console.print("  [error]Not ready.[/]")
        for f in critical_failures:
            console.print(f"    [error]✗[/] {f}")
        raise typer.Exit(code=1)
    else:
        console.print("  [ok]Ready.[/]")
        raise typer.Exit(code=0)
