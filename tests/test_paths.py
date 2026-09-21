"""Tests for viveka.core.paths."""

from __future__ import annotations

from pathlib import Path

from viveka.core.paths import (
    is_inside,
    project_config_path,
    project_dir,
    project_gitignore_path,
    project_properties_dir,
    user_db_path,
    user_state_dir,
)


class TestUserStatePaths:
    def test_user_state_dir_is_under_home(self) -> None:
        d = user_state_dir()
        assert d == Path.home() / ".viveka"

    def test_user_state_dir_is_created(self) -> None:
        d = user_state_dir()
        assert d.is_dir()

    def test_user_db_path_filename(self) -> None:
        assert user_db_path().name == "viveka.db"

    def test_user_db_path_parent_is_user_state(self) -> None:
        assert user_db_path().parent == user_state_dir()


class TestProjectStatePaths:
    def test_project_dir(self, tmp_path: Path) -> None:
        assert project_dir(tmp_path) == tmp_path / ".viveka"

    def test_project_config_path(self, tmp_path: Path) -> None:
        assert project_config_path(tmp_path) == tmp_path / ".viveka" / "config.yaml"

    def test_project_properties_dir(self, tmp_path: Path) -> None:
        assert project_properties_dir(tmp_path) == tmp_path / ".viveka" / "properties"

    def test_project_gitignore_path(self, tmp_path: Path) -> None:
        assert project_gitignore_path(tmp_path) == tmp_path / ".viveka" / ".gitignore"


class TestIsInside:
    def test_child_is_inside_parent(self, tmp_path: Path) -> None:
        child = tmp_path / "sub" / "file.txt"
        assert is_inside(child, tmp_path) is True

    def test_parent_itself_is_inside(self, tmp_path: Path) -> None:
        assert is_inside(tmp_path, tmp_path) is True

    def test_sibling_is_not_inside(self, tmp_path: Path) -> None:
        sibling = tmp_path.parent / "sibling"
        assert is_inside(sibling, tmp_path) is False

    def test_absolute_escape_is_not_inside(self, tmp_path: Path) -> None:
        assert is_inside(Path("/etc/passwd"), tmp_path) is False
