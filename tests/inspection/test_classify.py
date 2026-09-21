"""Tests for viveka.inspection.classify."""

from __future__ import annotations

from pathlib import Path

import pytest

from viveka.inspection.classify import (
    get_language_hint,
    is_binary_content,
    is_binary_extension,
    is_default_excluded_dir,
    is_default_excluded_file,
    is_sensitive_file,
)


class TestSensitiveFileDetection:
    @pytest.mark.parametrize(
        "filename",
        [
            ".env",
            ".env.local",
            ".env.production",
            "id_rsa",
            "id_rsa.pub",
            "id_ed25519",
            "server.key",
            "cert.pem",
            "bundle.p12",
            "identity.pfx",
            "credentials.json",
            "credentials.yaml",
            "secrets.json",
            "secrets.yml",
            "service-account.json",
            "service_account_key.json",
            "client_secret.json",
            "vault.kdbx",
        ],
    )
    def test_sensitive_files_flagged(self, filename: str) -> None:
        assert is_sensitive_file(filename) is True

    @pytest.mark.parametrize(
        "filename",
        [
            "app.py",
            "README.md",
            "pyproject.toml",
            "settings.py",
            "config.json",
            "environment.yml",
        ],
    )
    def test_non_sensitive_files_passed(self, filename: str) -> None:
        assert is_sensitive_file(filename) is False


class TestDefaultExclusions:
    @pytest.mark.parametrize(
        "dirname",
        [
            ".git",
            ".venv",
            "venv",
            "node_modules",
            "dist",
            "build",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".coverage",
            "mypackage.egg-info",
        ],
    )
    def test_default_excluded_dirs(self, dirname: str) -> None:
        assert is_default_excluded_dir(dirname) is True

    @pytest.mark.parametrize(
        "filename",
        [
            "app.pyc",
            "module.pyo",
            "helper.pyd",
            ".coverage",
            ".coverage.hostname.123",
            ".DS_Store",
            "Thumbs.db",
            "file.swp",
            "file.txt~",
        ],
    )
    def test_default_excluded_files(self, filename: str) -> None:
        assert is_default_excluded_file(filename) is True


class TestBinaryDetection:
    @pytest.mark.parametrize(
        "ext",
        [
            "png",
            "jpg",
            "jpeg",
            "gif",
            "zip",
            "tar",
            "gz",
            "whl",
            "exe",
            "so",
            "dll",
            "pdf",
            "db",
            "sqlite",
            "mp3",
            "mp4",
            "docx",
            "parquet",
        ],
    )
    def test_known_binary_extensions(self, ext: str) -> None:
        assert is_binary_extension(ext) is True

    def test_binary_content_null_byte_probe(self, tmp_path: Path) -> None:
        bin_file = tmp_path / "custom.dat"
        bin_file.write_bytes(b"HELLO\x00WORLD")
        assert is_binary_content(bin_file) is True

        txt_file = tmp_path / "custom_text.dat"
        txt_file.write_bytes(b"HELLO WORLD\nNO NULL BYTES HERE")
        assert is_binary_content(txt_file) is False


class TestLanguageHints:
    @pytest.mark.parametrize(
        ("filename", "ext", "expected"),
        [
            ("main.py", "py", "python"),
            ("data.json", "json", "json"),
            ("config.yaml", "yaml", "yaml"),
            ("config.yml", "yml", "yaml"),
            ("Cargo.toml", "toml", "toml"),
            ("README.md", "md", "markdown"),
            ("query.sql", "sql", "sql"),
            ("deploy.sh", "sh", "shell"),
            ("Dockerfile", "", "dockerfile"),
            ("Makefile", "", "makefile"),
            ("unknown.xyz", "xyz", None),
        ],
    )
    def test_language_hint_mapping(self, filename: str, ext: str, expected: str | None) -> None:
        assert get_language_hint(filename, ext) == expected
