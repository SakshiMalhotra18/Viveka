"""
File classification and security policy enforcement for VIVEKA.

Implements:
  - Hard security rules (sensitive secrets, keys, certs)
  - Default directories and runtime file exclusions
  - Binary file detection (extension mapping and bounded null-byte probe)
  - Size threshold evaluation
  - Language hint derivation
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

# ---------------------------------------------------------------------------
# Default Exclusions (Directories & Files)
# ---------------------------------------------------------------------------

DEFAULT_EXCLUDED_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        ".env_dir",
        "node_modules",
        "dist",
        "build",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".coverage",
        ".tox",
        ".nox",
        ".eggs",
        ".idea",
        ".vscode",
        ".cache",
    }
)

DEFAULT_EXCLUDED_FILE_PATTERNS: tuple[str, ...] = (
    ".coverage",
    ".coverage.*",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.egg-info",
    "*.swp",
    "*~",
    ".DS_Store",
    "Thumbs.db",
)


# ---------------------------------------------------------------------------
# Hard Security Exclusions (Secrets, Keys, Credentials)
# These CANNOT be overridden by --include or any ignore file.
# ---------------------------------------------------------------------------

SENSITIVE_FILE_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*.pkcs12",
    "*.crt",
    "*.cer",
    "*.der",
    "id_rsa",
    "id_rsa.*",
    "id_dsa",
    "id_dsa.*",
    "id_ecdsa",
    "id_ecdsa.*",
    "id_ed25519",
    "id_ed25519.*",
    "credentials",
    "credentials.*",
    "credentials*.json",
    "secrets",
    "secrets.*",
    "secrets*.json",
    "secrets*.yaml",
    "secrets*.yml",
    "service-account*.json",
    "service_account*.json",
    "client_secret*.json",
    "client_secrets*.json",
    "*.kdbx",
    "*.keystore",
    "*.jks",
)


# ---------------------------------------------------------------------------
# Binary File Extensions
# ---------------------------------------------------------------------------

KNOWN_BINARY_EXTENSIONS: frozenset[str] = frozenset(
    {
        # Compiled binaries / libraries
        "pyc",
        "pyo",
        "pyd",
        "so",
        "dll",
        "dylib",
        "exe",
        "bin",
        "o",
        "a",
        "class",
        "lib",
        "obj",
        # Archives / packages
        "zip",
        "tar",
        "gz",
        "bz2",
        "xz",
        "7z",
        "rar",
        "whl",
        "egg",
        "iso",
        "dmg",
        # Images
        "png",
        "jpg",
        "jpeg",
        "gif",
        "webp",
        "ico",
        "bmp",
        "tiff",
        "tif",
        "psd",
        "ai",
        "raw",
        # Media (audio / video)
        "mp3",
        "mp4",
        "wav",
        "avi",
        "mov",
        "mkv",
        "flv",
        "ogg",
        "flac",
        "m4a",
        "webm",
        # Documents / Database
        "pdf",
        "db",
        "sqlite",
        "sqlite3",
        "parquet",
        "arrow",
        "feather",
        # Office
        "docx",
        "xlsx",
        "pptx",
        "doc",
        "xls",
        "ppt",
        # Fonts
        "woff",
        "woff2",
        "ttf",
        "eot",
        "otf",
    }
)


# ---------------------------------------------------------------------------
# Language Hints
# ---------------------------------------------------------------------------

_LANGUAGE_MAP: dict[str, str] = {
    "py": "python",
    "pyi": "python",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
    "md": "markdown",
    "txt": "text",
    "rst": "rst",
    "sql": "sql",
    "sh": "shell",
    "bash": "shell",
    "zsh": "shell",
    "js": "javascript",
    "jsx": "javascript",
    "ts": "typescript",
    "tsx": "typescript",
    "html": "html",
    "htm": "html",
    "css": "css",
    "scss": "scss",
    "sass": "sass",
    "xml": "xml",
    "csv": "csv",
    "tsv": "tsv",
    "c": "c",
    "h": "c",
    "cpp": "cpp",
    "hpp": "cpp",
    "cc": "cpp",
    "rs": "rust",
    "go": "go",
    "java": "java",
    "rb": "ruby",
    "php": "php",
    "graphql": "graphql",
    "gql": "graphql",
    "proto": "protobuf",
    "dockerfile": "dockerfile",
}


def is_sensitive_file(filename: str) -> bool:
    """Return True if filename matches any known sensitive credential or key pattern."""
    lower_name = filename.lower()
    for pat in SENSITIVE_FILE_PATTERNS:
        if fnmatch.fnmatch(lower_name, pat.lower()):
            return True
    return False


def is_default_excluded_dir(dir_name: str) -> bool:
    """Return True if directory name is in the default exclusion list."""
    return dir_name in DEFAULT_EXCLUDED_DIR_NAMES or dir_name.endswith(".egg-info")


def is_default_excluded_file(filename: str) -> bool:
    """Return True if filename matches any default file exclusion pattern."""
    for pat in DEFAULT_EXCLUDED_FILE_PATTERNS:
        if fnmatch.fnmatch(filename, pat):
            return True
    return False


def is_binary_extension(ext: str) -> bool:
    """Return True if extension is a known binary file extension."""
    return ext.lower() in KNOWN_BINARY_EXTENSIONS


def is_binary_content(file_path: Path, max_bytes: int = 1024) -> bool:
    """Perform a small bounded read checking for null bytes.

    Never reads more than *max_bytes*.
    Returns False if file cannot be read.
    """
    try:
        with file_path.open("rb") as f:
            chunk = f.read(max_bytes)
        return b"\x00" in chunk
    except OSError:
        return False


def get_language_hint(filename: str, ext: str) -> str | None:
    """Infer a programming or markup language hint from filename and extension."""
    lower_name = filename.lower()
    if lower_name == "dockerfile" or lower_name.startswith("dockerfile."):
        return "dockerfile"
    if lower_name == "makefile":
        return "makefile"
    if lower_name in ("jenkinsfile", "vagrantfile"):
        return "groovy"
    return _LANGUAGE_MAP.get(ext.lower())
