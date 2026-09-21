"""
Data models for repository inspection.

Provides typed representations for scanned files, decisions, reasons,
and repository-level scan summaries.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class Decision(StrEnum):
    """Action decision for a scanned file."""

    INCLUDE = "include"
    EXCLUDE = "exclude"
    SKIP = "skip"
    SENSITIVE = "sensitive"


class Reason(StrEnum):
    """Detailed justification for a scanner decision."""

    INCLUDED = "included"
    GITIGNORE = "gitignore"
    VIVEKAIGNORE = "vivekaignore"
    CLI_EXCLUDE = "cli_exclude"
    DEFAULT_EXCLUSION = "default_exclusion"
    SENSITIVE_FILE = "sensitive_file"
    BINARY_FILE = "binary_file"
    FILE_TOO_LARGE = "file_too_large"
    SYMLINK = "symlink"
    BROKEN_SYMLINK = "broken_symlink"
    OUTSIDE_ROOT = "outside_root"
    SYMLINK_LOOP = "symlink_loop"
    INACCESSIBLE = "inaccessible"
    USER_STATE = "user_state"
    NOT_INCLUDED = "not_included"


class ScannedFile(BaseModel):
    """A single file discovered during repository inspection."""

    relative_path: str = Field(
        description="Normalized POSIX relative path from repository root (e.g. 'src/app.py')."
    )
    size_bytes: int = Field(ge=0, description="File size in bytes.")
    extension: str = Field(
        description="File extension without leading dot (lowercase), or empty string."
    )
    decision: Decision = Field(description="Action decision for this file.")
    reason: Reason = Field(description="Detailed reason for the decision.")
    is_symlink: bool = Field(default=False, description="Whether the file path is a symbolic link.")
    language_hint: str | None = Field(
        default=None,
        description="Trivially inferred programming or markup language, if any.",
    )


class ScanSummary(BaseModel):
    """Structured summary of a repository inspection run."""

    root: str = Field(description="Absolute path to the inspected repository root.")
    files_seen: int = Field(ge=0, description="Total files and links visited.")
    files_selected: int = Field(ge=0, description="Files selected for future inspection.")
    files_excluded: int = Field(
        ge=0, description="Files excluded by ignore rules or default filters."
    )
    sensitive_files_detected: int = Field(
        ge=0, description="Sensitive credential or key files identified."
    )
    binary_files_skipped: int = Field(ge=0, description="Binary or media files skipped.")
    oversized_files_skipped: int = Field(ge=0, description="Files exceeding size limit skipped.")
    symlinks_skipped: int = Field(ge=0, description="Symbolic links skipped for safety.")
    warnings: list[str] = Field(
        default_factory=list, description="Non-fatal warnings encountered during scan."
    )
    selected_files: list[ScannedFile] = Field(
        default_factory=list, description="List of files approved for inspection."
    )
    all_files: list[ScannedFile] = Field(
        default_factory=list, description="Complete inventory of all discovered paths."
    )
