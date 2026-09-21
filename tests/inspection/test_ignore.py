"""Tests for viveka.inspection.ignore."""

from __future__ import annotations

from pathlib import Path

from viveka.inspection.ignore import IgnoreEngine


class TestIgnoreEngine:
    def test_gitignore_file_matching(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("*.log\ntemp/\n", encoding="utf-8")
        engine = IgnoreEngine(root=tmp_path, honor_gitignore=True)

        assert engine.is_gitignored("debug.log") is True
        assert engine.is_gitignored("src/debug.log") is True
        assert engine.is_gitignored("temp", is_dir=True) is True
        assert engine.is_gitignored("temp/file.txt") is True
        assert engine.is_gitignored("src/main.py") is False

    def test_honor_gitignore_false_ignores_file(self, tmp_path: Path) -> None:
        (tmp_path / ".gitignore").write_text("*.log\n", encoding="utf-8")
        engine = IgnoreEngine(root=tmp_path, honor_gitignore=False)

        assert engine.is_gitignored("debug.log") is False

    def test_vivekaignore_matching(self, tmp_path: Path) -> None:
        (tmp_path / ".vivekaignore").write_text("fixtures/\nlocal_data.csv\n", encoding="utf-8")
        engine = IgnoreEngine(root=tmp_path)

        assert engine.is_vivekaignored("fixtures", is_dir=True) is True
        assert engine.is_vivekaignored("fixtures/mock.json") is True
        assert engine.is_vivekaignored("local_data.csv") is True
        assert engine.is_vivekaignored("src/agent.py") is False

    def test_cli_exclude_matching(self, tmp_path: Path) -> None:
        engine = IgnoreEngine(root=tmp_path, cli_excludes=["legacy/", "*.bak"])

        assert engine.is_cli_excluded("legacy", is_dir=True) is True
        assert engine.is_cli_excluded("legacy/old.py") is True
        assert engine.is_cli_excluded("main.py.bak") is True
        assert engine.is_cli_excluded("main.py") is False

    def test_cli_include_matching(self, tmp_path: Path) -> None:
        engine = IgnoreEngine(root=tmp_path, cli_includes=["src/**", "pyproject.toml"])

        assert engine.is_cli_included("src/agent.py") is True
        assert engine.is_cli_included("pyproject.toml") is True
        assert engine.is_cli_included("tests/test_agent.py") is False

    def test_no_cli_includes_defaults_to_all_included(self, tmp_path: Path) -> None:
        engine = IgnoreEngine(root=tmp_path, cli_includes=None)

        assert engine.is_cli_included("src/agent.py") is True
        assert engine.is_cli_included("tests/test_agent.py") is True
