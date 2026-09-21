"""
VIVEKA root Typer application.

Entry point declared in pyproject.toml:
  [project.scripts]
  viveka = "viveka.cli.app:app"

Command registration pattern:
  - Each command lives in its own module under viveka.cli.commands/.
  - Commands are registered here by calling app.command().
  - The root callback handles --version and prints help on bare invocation.

To add a new command in a future phase:
  1. Create viveka/cli/commands/mynewcommand.py with a function my_new_command().
  2. Add  app.command("my-new-command")(commands.mynewcommand.my_new_command)  here.
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

import typer

from viveka.cli.commands import (
    demo,
    diagnose,
    doctor,
    evaluate,
    init_,
    inspect,
    properties,
    reduce,
    regression,
    replay,
    suggest,
    verify,
    version,
    worlds,
)
from viveka.core.errors import VivekaError
from viveka.reporting.console import console

app = typer.Typer(
    name="viveka",
    help=(
        "VIVEKA · विवेक — Property-based verification engine for AI agents.\n\n"
        "Run [bold]viveka init[/] to get started in a project directory."
    ),
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=True,
    pretty_exceptions_enable=False,  # We handle VivekaError ourselves
)

# ---------------------------------------------------------------------------
# Register commands
# ---------------------------------------------------------------------------

app.command("version", help="Show VIVEKA and Python version.")(version.version_command)
app.command("init", help="Initialise VIVEKA in a project directory.")(init_.init_command)
app.command("doctor", help="Check environment readiness.")(doctor.doctor_command)
app.command("inspect", help="Safely inspect repository structure and discovered files.")(
    inspect.inspect_command
)
app.add_typer(properties.properties_app, name="properties")
app.add_typer(worlds.worlds_app, name="worlds")
app.add_typer(demo.demo_app, name="demo")
app.command("evaluate", help="Evaluate approved property oracles against test worlds.")(
    evaluate.evaluate_command
)
app.command("reduce", help="Greedily reduce a failing World to a Reduced Failure World.")(
    reduce.reduce_command
)
app.command("diagnose", help="Produce evidence-based diagnosis of a failure.")(
    diagnose.diagnose_command
)
app.add_typer(regression.regression_app, name="regression")
app.command("replay", help="Replay a saved behavioral regression.")(replay.replay_command)
app.add_typer(suggest.suggest_app, name="suggest")
app.command("verify", help="Run property-based verification against the target AI agent.")(
    verify.verify_command
)

# ---------------------------------------------------------------------------
# Future commands — placeholders for discoverability (viveka --help)
# These raise NotImplementedError until implemented in their respective phase.
# ---------------------------------------------------------------------------

_PLANNED = {
    "show": "Show a stored object (trial, counterexample, regression).",
    "config": "Show or validate project configuration.",
}


def _make_placeholder(cmd_name: str, description: str) -> None:
    @app.command(cmd_name, help=description)
    def _placeholder(
        ctx: typer.Context = typer.Option(None, hidden=True),
    ) -> None:
        console.print(
            f"[warn]`viveka {cmd_name}` is not yet implemented.[/]\n"
            f"[muted]{description}[/]\n\n"
            "Track progress: https://github.com/SakshiMalhotra18/Viveka"
        )
        raise typer.Exit(code=2)

    _placeholder.__name__ = f"_placeholder_{cmd_name}"


for _name, _desc in _PLANNED.items():
    _make_placeholder(_name, _desc)


# ---------------------------------------------------------------------------
# Global error handler
# ---------------------------------------------------------------------------


def main() -> None:
    """Wrap app() to catch VivekaError and render it cleanly."""
    try:
        app()
    except VivekaError as exc:
        console.print(f"\n[error]Error:[/] {exc.message}")
        if exc.hint:
            console.print(f"[muted]  → {exc.hint}[/]")
        raise SystemExit(2) from None
