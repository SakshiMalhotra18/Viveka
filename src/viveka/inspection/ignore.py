"""
Ignore engine for VIVEKA repository inspection.

Handles pattern compilation and matching for:
  - .vivekaignore files (VIVEKA-specific)
  - .gitignore files (standard gitwildmatch syntax)
  - CLI --exclude patterns
  - CLI --include patterns

Uses pathspec (pure Python, standard gitwildmatch specification).
"""

from __future__ import annotations

from pathlib import Path

import pathspec


class IgnoreEngine:
    """Evaluates ignore patterns from ignore files and CLI options."""

    def __init__(
        self,
        root: Path,
        honor_gitignore: bool = True,
        vivekaignore_file: str = ".vivekaignore",
        cli_excludes: list[str] | None = None,
        cli_includes: list[str] | None = None,
    ) -> None:
        self.root = root.resolve()
        self.honor_gitignore = honor_gitignore

        # 1. CLI exclude spec
        self._cli_exclude_spec = (
            pathspec.PathSpec.from_lines("gitignore", cli_excludes) if cli_excludes else None
        )

        # 2. .vivekaignore spec
        vivekaignore_path = self.root / vivekaignore_file
        self._vivekaignore_spec = self._load_spec_file(vivekaignore_path)

        # 3. .gitignore spec
        gitignore_path = self.root / ".gitignore"
        self._gitignore_spec = self._load_spec_file(gitignore_path) if honor_gitignore else None

        # 4. CLI include spec
        self.has_cli_includes = bool(cli_includes)
        self._cli_include_spec = (
            pathspec.PathSpec.from_lines("gitignore", cli_includes) if cli_includes else None
        )

    @staticmethod
    def _load_spec_file(file_path: Path) -> pathspec.PathSpec | None:
        """Load and compile a gitignore-style file if it exists."""
        if not file_path.is_file():
            return None
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            return pathspec.PathSpec.from_lines("gitignore", content.splitlines())
        except OSError:
            return None

    @staticmethod
    def _match_path(spec: pathspec.PathSpec | None, rel_path: str, is_dir: bool = False) -> bool:
        """Check if relative POSIX path matches spec (accounting for directory semantics)."""
        if spec is None:
            return False
        # Normalize to POSIX relative path
        clean_path = rel_path.strip("/\\").replace("\\", "/")
        if not clean_path:
            return False

        if spec.match_file(clean_path):
            return True
        if is_dir and spec.match_file(f"{clean_path}/"):
            return True
        return False

    def is_cli_excluded(self, rel_path: str, is_dir: bool = False) -> bool:
        """Check if path matches CLI --exclude patterns."""
        return self._match_path(self._cli_exclude_spec, rel_path, is_dir)

    def is_vivekaignored(self, rel_path: str, is_dir: bool = False) -> bool:
        """Check if path matches .vivekaignore patterns."""
        return self._match_path(self._vivekaignore_spec, rel_path, is_dir)

    def is_gitignored(self, rel_path: str, is_dir: bool = False) -> bool:
        """Check if path matches .gitignore patterns."""
        return self._match_path(self._gitignore_spec, rel_path, is_dir)

    def is_cli_included(self, rel_path: str, is_dir: bool = False) -> bool:
        """Check if path matches CLI --include patterns (when specified)."""
        if not self.has_cli_includes or self._cli_include_spec is None:
            return True
        return self._match_path(self._cli_include_spec, rel_path, is_dir)
