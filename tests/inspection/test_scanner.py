"""Tests for the repository scanner engine."""

from __future__ import annotations

import hashlib
from pathlib import Path

from viveka.inspection.models import Decision, Reason
from viveka.inspection.scanner import scan_repository


def _compute_dir_hash(directory: Path) -> dict[str, str]:
    """Compute sha256 hashes of all files in directory to verify non-mutation."""
    hashes = {}
    for p in sorted(directory.rglob("*")):
        if p.is_file():
            hashes[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashes


class TestScanner:
    def test_ordinary_project_traversal(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
        (tmp_path / "README.md").write_text("# Demo Project\n", encoding="utf-8")
        src = tmp_path / "src"
        src.mkdir()
        (src / "agent.py").write_text("def run(): pass\n", encoding="utf-8")
        (src / "tools.py").write_text("def tool(): pass\n", encoding="utf-8")

        summary = scan_repository(root=tmp_path)

        assert summary.files_seen == 4
        assert summary.files_selected == 4
        assert summary.files_excluded == 0
        selected_paths = [f.relative_path for f in summary.selected_files]
        assert selected_paths == [
            "README.md",
            "pyproject.toml",
            "src/agent.py",
            "src/tools.py",
        ]

    def test_default_exclusions(self, tmp_path: Path) -> None:
        # Standard files
        (tmp_path / "app.py").write_text("print('hello')", encoding="utf-8")

        # Excluded directories
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("core.bare=false", encoding="utf-8")

        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()
        (venv_dir / "pyvenv.cfg").write_text("version=3.12", encoding="utf-8")

        node_dir = tmp_path / "node_modules"
        node_dir.mkdir()
        (node_dir / "package.json").write_text("{}", encoding="utf-8")

        summary = scan_repository(root=tmp_path)

        assert summary.files_selected == 1
        assert summary.selected_files[0].relative_path == "app.py"
        assert summary.files_excluded >= 3

    def test_sensitive_file_protection(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("print(1)", encoding="utf-8")
        (tmp_path / ".env").write_text("API_KEY=super_secret_value", encoding="utf-8")
        (tmp_path / "credentials.json").write_text('{"secret": "val"}', encoding="utf-8")
        (tmp_path / "id_rsa").write_text("---PRIVATE KEY---", encoding="utf-8")

        summary = scan_repository(root=tmp_path)

        assert summary.files_selected == 1
        assert summary.selected_files[0].relative_path == "app.py"
        assert summary.sensitive_files_detected == 3

        sensitive_paths = [
            f.relative_path for f in summary.all_files if f.decision == Decision.SENSITIVE
        ]
        assert sorted(sensitive_paths) == [".env", "credentials.json", "id_rsa"]

    def test_file_size_limit_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "normal.txt").write_text("small text", encoding="utf-8")
        big_file = tmp_path / "giant.txt"
        big_file.write_bytes(b"A" * 600 * 1024)  # 600 KB > default 512 KB

        summary = scan_repository(root=tmp_path, max_file_size_kb=512)

        assert summary.files_selected == 1
        assert summary.selected_files[0].relative_path == "normal.txt"
        assert summary.oversized_files_skipped == 1

        oversized = [f for f in summary.all_files if f.reason == Reason.FILE_TOO_LARGE]
        assert len(oversized) == 1
        assert oversized[0].relative_path == "giant.txt"

    def test_empty_repository(self, tmp_path: Path) -> None:
        summary = scan_repository(root=tmp_path)
        assert summary.files_seen == 0
        assert summary.files_selected == 0
        assert summary.files_excluded == 0
        assert summary.warnings == []

    def test_unicode_filenames(self, tmp_path: Path) -> None:
        (tmp_path / "विवेक.py").write_text("print('viveka')", encoding="utf-8")
        (tmp_path / "dokument_äöü.txt").write_text("unicode text", encoding="utf-8")

        summary = scan_repository(root=tmp_path)
        assert summary.files_selected == 2

    def test_deterministic_ordering(self, tmp_path: Path) -> None:
        (tmp_path / "z_file.py").write_text("z", encoding="utf-8")
        (tmp_path / "a_file.py").write_text("a", encoding="utf-8")
        (tmp_path / "m_file.py").write_text("m", encoding="utf-8")

        summary1 = scan_repository(root=tmp_path)
        summary2 = scan_repository(root=tmp_path)

        paths1 = [f.relative_path for f in summary1.all_files]
        paths2 = [f.relative_path for f in summary2.all_files]

        assert paths1 == ["a_file.py", "m_file.py", "z_file.py"]
        assert paths1 == paths2

    def test_scanner_never_modifies_target_repository(self, tmp_path: Path) -> None:
        (tmp_path / "source.py").write_text("import os", encoding="utf-8")
        (tmp_path / ".env").write_text("SECRET=1", encoding="utf-8")
        (tmp_path / "data.bin").write_bytes(b"\x00\x01\x02")

        before_hashes = _compute_dir_hash(tmp_path)
        scan_repository(root=tmp_path)
        after_hashes = _compute_dir_hash(tmp_path)

        assert before_hashes == after_hashes
