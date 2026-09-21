"""Tests for path safety, symlink containment, and traversal security."""

from __future__ import annotations

from pathlib import Path

import pytest

from viveka.inspection.models import Decision, Reason
from viveka.inspection.scanner import scan_repository


class TestPathSafety:
    def test_nonexistent_root_raises_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent"
        with pytest.raises(FileNotFoundError):
            scan_repository(root=missing)

    def test_file_root_raises_not_a_directory(self, tmp_path: Path) -> None:
        file_path = tmp_path / "file.txt"
        file_path.write_text("content", encoding="utf-8")
        with pytest.raises(NotADirectoryError):
            scan_repository(root=file_path)

    def test_symlink_skipped_by_default(self, tmp_path: Path) -> None:
        target = tmp_path / "target.py"
        target.write_text("print('hello')", encoding="utf-8")
        link = tmp_path / "link.py"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported in this test environment")

        summary = scan_repository(root=tmp_path, follow_symlinks=False)
        link_entries = [f for f in summary.all_files if f.relative_path == "link.py"]
        assert len(link_entries) == 1
        assert link_entries[0].decision == Decision.SKIP
        assert link_entries[0].reason == Reason.SYMLINK
        assert link_entries[0].is_symlink is True

    def test_symlink_outside_root_is_blocked(self, tmp_path: Path) -> None:
        external_dir = tmp_path.parent / "external_secret_dir"
        external_dir.mkdir(exist_ok=True)
        external_file = external_dir / "secret.txt"
        external_file.write_text("sensitive", encoding="utf-8")

        repo_dir = tmp_path / "my_repo"
        repo_dir.mkdir()
        link = repo_dir / "escape_link.txt"
        try:
            link.symlink_to(external_file)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported in this test environment")

        summary = scan_repository(root=repo_dir, follow_symlinks=True)
        link_entries = [f for f in summary.all_files if f.relative_path == "escape_link.txt"]
        assert len(link_entries) == 1
        assert link_entries[0].decision == Decision.SKIP
        assert link_entries[0].reason == Reason.OUTSIDE_ROOT
        assert any("outside" in w.lower() for w in summary.warnings)

    def test_broken_symlink_warns_and_does_not_crash(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does_not_exist.py"
        link = tmp_path / "broken_link.py"
        try:
            link.symlink_to(nonexistent)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported in this test environment")

        summary = scan_repository(root=tmp_path, follow_symlinks=True)
        link_entries = [f for f in summary.all_files if f.relative_path == "broken_link.py"]
        assert len(link_entries) == 1
        assert link_entries[0].decision == Decision.SKIP
        assert link_entries[0].reason == Reason.BROKEN_SYMLINK

    def test_symlink_directory_loop_prevention(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        loop_link = sub / "loop"
        try:
            loop_link.symlink_to(tmp_path, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("Directory symlinks not supported in this test environment")

        # Must not hang in infinite loop or crash
        summary = scan_repository(root=tmp_path, follow_symlinks=True)
        assert summary.files_seen >= 0
