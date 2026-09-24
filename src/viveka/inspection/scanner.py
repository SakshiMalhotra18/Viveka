"""
Safe repository scanner for VIVEKA.

Traverses repository directories, applies ignore rules and security policies,
and compiles a deterministic file inventory without executing or importing any
target repository code.
"""

from __future__ import annotations

import os
from pathlib import Path

from viveka.core.config import VivekaConfig
from viveka.core.paths import is_inside, user_state_dir
from viveka.inspection.classify import (
    get_language_hint,
    is_binary_content,
    is_binary_extension,
    is_default_excluded_dir,
    is_default_excluded_file,
    is_sensitive_file,
    is_virtualenv_dir,
    is_viveka_artifact_dir,
    is_viveka_artifact_file,
)
from viveka.inspection.ignore import IgnoreEngine
from viveka.inspection.models import Decision, Reason, ScannedFile, ScanSummary


def scan_repository(
    root: Path,
    config: VivekaConfig | None = None,
    cli_includes: list[str] | None = None,
    cli_excludes: list[str] | None = None,
    follow_symlinks: bool | None = None,
    max_file_size_kb: int | None = None,
) -> ScanSummary:
    """Safely inspect repository files and classify them.

    Args:
        root: Target repository root path.
        config: Optional loaded VIVEKA configuration.
        cli_includes: Optional list of CLI include patterns.
        cli_excludes: Optional list of CLI exclude patterns.
        follow_symlinks: Override for follow_symlinks setting.
        max_file_size_kb: Override for max_file_size_kb setting.

    Returns:
        Structured :class:`ScanSummary` containing discovery details and decisions.
    """
    resolved_root = root.resolve()
    if not resolved_root.exists():
        raise FileNotFoundError(f"Repository path does not exist: {root}")
    if not resolved_root.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: {root}")

    # Determine settings from config or defaults
    insp_cfg = config.inspection if config else None
    honor_gitignore = insp_cfg.honor_gitignore if insp_cfg else True
    vivekaignore_file = insp_cfg.vivekaignore if insp_cfg else ".vivekaignore"
    eff_follow_symlinks = (
        follow_symlinks
        if follow_symlinks is not None
        else (insp_cfg.follow_symlinks if insp_cfg else False)
    )
    eff_max_size_kb = (
        max_file_size_kb
        if max_file_size_kb is not None
        else (insp_cfg.max_file_size_kb if insp_cfg else 512)
    )
    max_size_bytes = eff_max_size_kb * 1024

    # Ignore engine
    ignore_engine = IgnoreEngine(
        root=resolved_root,
        honor_gitignore=honor_gitignore,
        vivekaignore_file=vivekaignore_file,
        cli_excludes=cli_excludes,
        cli_includes=cli_includes,
    )

    warnings: list[str] = []
    all_files: list[ScannedFile] = []
    selected_files: list[ScannedFile] = []

    # Visited tracking for loop prevention
    visited_dirs: set[str] = set()
    user_state = user_state_dir().resolve()

    def _to_posix_rel(p: Path) -> str:
        try:
            rel = p.relative_to(resolved_root)
            return str(rel).replace("\\", "/")
        except ValueError:
            return p.name

    # Recursive directory walker
    def _walk_dir(current_dir: Path) -> None:
        try:
            canonical_current = str(current_dir.resolve())
        except OSError as exc:
            warnings.append(f"Inaccessible directory: {current_dir} ({exc})")
            return

        if canonical_current in visited_dirs:
            warnings.append(f"Directory loop detected at: {current_dir}")
            return
        visited_dirs.add(canonical_current)

        try:
            entries = sorted(os.scandir(current_dir), key=lambda e: e.name)
        except (PermissionError, OSError) as exc:
            warnings.append(f"Permission denied accessing: {current_dir} ({exc})")
            return

        subdirs_to_visit: list[Path] = []

        for entry in entries:
            entry_path = Path(entry.path)
            rel_path = _to_posix_rel(entry_path)

            # Check if this is the user state directory (~/.viveka)
            try:
                if entry_path.resolve() == user_state:
                    all_files.append(
                        ScannedFile(
                            relative_path=rel_path,
                            size_bytes=0,
                            extension="",
                            decision=Decision.EXCLUDE,
                            reason=Reason.USER_STATE,
                        )
                    )
                    continue
            except OSError:
                pass

            try:
                is_symlink = entry.is_symlink()
            except OSError:
                is_symlink = False

            try:
                is_dir = entry.is_dir(follow_symlinks=eff_follow_symlinks)
            except OSError:
                is_dir = False

            if is_dir:
                # Evaluate directory exclusion rules
                dir_name = entry.name
                if is_default_excluded_dir(dir_name):
                    all_files.append(
                        ScannedFile(
                            relative_path=rel_path,
                            size_bytes=0,
                            extension="",
                            decision=Decision.EXCLUDE,
                            reason=Reason.DEFAULT_EXCLUSION,
                            is_symlink=is_symlink,
                        )
                    )
                    continue

                if is_virtualenv_dir(entry_path):
                    all_files.append(
                        ScannedFile(
                            relative_path=rel_path,
                            size_bytes=0,
                            extension="",
                            decision=Decision.EXCLUDE,
                            reason=Reason.DEFAULT_EXCLUSION,
                            is_symlink=is_symlink,
                        )
                    )
                    continue

                if is_viveka_artifact_dir(rel_path):
                    all_files.append(
                        ScannedFile(
                            relative_path=rel_path,
                            size_bytes=0,
                            extension="",
                            decision=Decision.EXCLUDE,
                            reason=Reason.DEFAULT_EXCLUSION,
                            is_symlink=is_symlink,
                        )
                    )
                    continue

                if ignore_engine.is_cli_excluded(rel_path, is_dir=True):
                    all_files.append(
                        ScannedFile(
                            relative_path=rel_path,
                            size_bytes=0,
                            extension="",
                            decision=Decision.EXCLUDE,
                            reason=Reason.CLI_EXCLUDE,
                            is_symlink=is_symlink,
                        )
                    )
                    continue

                if ignore_engine.is_vivekaignored(rel_path, is_dir=True):
                    all_files.append(
                        ScannedFile(
                            relative_path=rel_path,
                            size_bytes=0,
                            extension="",
                            decision=Decision.EXCLUDE,
                            reason=Reason.VIVEKAIGNORE,
                            is_symlink=is_symlink,
                        )
                    )
                    continue

                if ignore_engine.is_gitignored(rel_path, is_dir=True):
                    all_files.append(
                        ScannedFile(
                            relative_path=rel_path,
                            size_bytes=0,
                            extension="",
                            decision=Decision.EXCLUDE,
                            reason=Reason.GITIGNORE,
                            is_symlink=is_symlink,
                        )
                    )
                    continue

                # Handle directory symlinks
                if is_symlink:
                    if not eff_follow_symlinks:
                        all_files.append(
                            ScannedFile(
                                relative_path=rel_path,
                                size_bytes=0,
                                extension="",
                                decision=Decision.SKIP,
                                reason=Reason.SYMLINK,
                                is_symlink=True,
                            )
                        )
                        continue

                    try:
                        resolved_target = entry_path.resolve()
                    except OSError:
                        warnings.append(f"Broken directory symlink: {rel_path}")
                        all_files.append(
                            ScannedFile(
                                relative_path=rel_path,
                                size_bytes=0,
                                extension="",
                                decision=Decision.SKIP,
                                reason=Reason.BROKEN_SYMLINK,
                                is_symlink=True,
                            )
                        )
                        continue

                    if not resolved_target.exists():
                        warnings.append(f"Broken directory symlink: {rel_path}")
                        all_files.append(
                            ScannedFile(
                                relative_path=rel_path,
                                size_bytes=0,
                                extension="",
                                decision=Decision.SKIP,
                                reason=Reason.BROKEN_SYMLINK,
                                is_symlink=True,
                            )
                        )
                        continue

                    if not is_inside(resolved_target, resolved_root):
                        warnings.append(f"Directory symlink points outside repository: {rel_path}")
                        all_files.append(
                            ScannedFile(
                                relative_path=rel_path,
                                size_bytes=0,
                                extension="",
                                decision=Decision.SKIP,
                                reason=Reason.OUTSIDE_ROOT,
                                is_symlink=True,
                            )
                        )
                        continue

                subdirs_to_visit.append(entry_path)

            else:
                # File handling
                filename = entry.name
                ext = filename.rsplit(".", 1)[-1].lower() if "." in filename[1:] else ""
                lang_hint = get_language_hint(filename, ext)

                try:
                    stat = entry.stat(follow_symlinks=eff_follow_symlinks)
                    size_bytes = stat.st_size
                except (PermissionError, OSError):
                    size_bytes = 0

                # 1. Hard Security Exclusion (inviolable)
                if is_sensitive_file(filename):
                    scanned = ScannedFile(
                        relative_path=rel_path,
                        size_bytes=size_bytes,
                        extension=ext,
                        decision=Decision.SENSITIVE,
                        reason=Reason.SENSITIVE_FILE,
                        is_symlink=is_symlink,
                        language_hint=lang_hint,
                    )
                    all_files.append(scanned)
                    continue

                # 2. CLI Excludes
                if ignore_engine.is_cli_excluded(rel_path, is_dir=False):
                    scanned = ScannedFile(
                        relative_path=rel_path,
                        size_bytes=size_bytes,
                        extension=ext,
                        decision=Decision.EXCLUDE,
                        reason=Reason.CLI_EXCLUDE,
                        is_symlink=is_symlink,
                        language_hint=lang_hint,
                    )
                    all_files.append(scanned)
                    continue

                # 3. .vivekaignore
                if ignore_engine.is_vivekaignored(rel_path, is_dir=False):
                    scanned = ScannedFile(
                        relative_path=rel_path,
                        size_bytes=size_bytes,
                        extension=ext,
                        decision=Decision.EXCLUDE,
                        reason=Reason.VIVEKAIGNORE,
                        is_symlink=is_symlink,
                        language_hint=lang_hint,
                    )
                    all_files.append(scanned)
                    continue

                # 4. .gitignore
                if ignore_engine.is_gitignored(rel_path, is_dir=False):
                    scanned = ScannedFile(
                        relative_path=rel_path,
                        size_bytes=size_bytes,
                        extension=ext,
                        decision=Decision.EXCLUDE,
                        reason=Reason.GITIGNORE,
                        is_symlink=is_symlink,
                        language_hint=lang_hint,
                    )
                    all_files.append(scanned)
                    continue

                # 5. Default File Exclusions
                if is_default_excluded_file(filename) or is_viveka_artifact_file(rel_path):
                    scanned = ScannedFile(
                        relative_path=rel_path,
                        size_bytes=size_bytes,
                        extension=ext,
                        decision=Decision.EXCLUDE,
                        reason=Reason.DEFAULT_EXCLUSION,
                        is_symlink=is_symlink,
                        language_hint=lang_hint,
                    )
                    all_files.append(scanned)
                    continue

                # 6. CLI Includes
                if not ignore_engine.is_cli_included(rel_path, is_dir=False):
                    scanned = ScannedFile(
                        relative_path=rel_path,
                        size_bytes=size_bytes,
                        extension=ext,
                        decision=Decision.EXCLUDE,
                        reason=Reason.NOT_INCLUDED,
                        is_symlink=is_symlink,
                        language_hint=lang_hint,
                    )
                    all_files.append(scanned)
                    continue

                # 7. Symlink Safety
                if is_symlink:
                    if not eff_follow_symlinks:
                        scanned = ScannedFile(
                            relative_path=rel_path,
                            size_bytes=size_bytes,
                            extension=ext,
                            decision=Decision.SKIP,
                            reason=Reason.SYMLINK,
                            is_symlink=True,
                            language_hint=lang_hint,
                        )
                        all_files.append(scanned)
                        continue

                    try:
                        resolved_file = entry_path.resolve()
                    except OSError:
                        warnings.append(f"Broken symlink: {rel_path}")
                        scanned = ScannedFile(
                            relative_path=rel_path,
                            size_bytes=size_bytes,
                            extension=ext,
                            decision=Decision.SKIP,
                            reason=Reason.BROKEN_SYMLINK,
                            is_symlink=True,
                            language_hint=lang_hint,
                        )
                        all_files.append(scanned)
                        continue

                    if not resolved_file.exists():
                        warnings.append(f"Broken symlink: {rel_path}")
                        scanned = ScannedFile(
                            relative_path=rel_path,
                            size_bytes=size_bytes,
                            extension=ext,
                            decision=Decision.SKIP,
                            reason=Reason.BROKEN_SYMLINK,
                            is_symlink=True,
                            language_hint=lang_hint,
                        )
                        all_files.append(scanned)
                        continue

                    if not is_inside(resolved_file, resolved_root):
                        warnings.append(f"Symlink points outside repository: {rel_path}")
                        scanned = ScannedFile(
                            relative_path=rel_path,
                            size_bytes=size_bytes,
                            extension=ext,
                            decision=Decision.SKIP,
                            reason=Reason.OUTSIDE_ROOT,
                            is_symlink=True,
                            language_hint=lang_hint,
                        )
                        all_files.append(scanned)
                        continue

                # 8. File Size Limit
                if size_bytes > max_size_bytes:
                    scanned = ScannedFile(
                        relative_path=rel_path,
                        size_bytes=size_bytes,
                        extension=ext,
                        decision=Decision.SKIP,
                        reason=Reason.FILE_TOO_LARGE,
                        is_symlink=is_symlink,
                        language_hint=lang_hint,
                    )
                    all_files.append(scanned)
                    continue

                # 9. Binary File Check
                if is_binary_extension(ext) or is_binary_content(entry_path):
                    scanned = ScannedFile(
                        relative_path=rel_path,
                        size_bytes=size_bytes,
                        extension=ext,
                        decision=Decision.SKIP,
                        reason=Reason.BINARY_FILE,
                        is_symlink=is_symlink,
                        language_hint=lang_hint,
                    )
                    all_files.append(scanned)
                    continue

                # 10. Included
                scanned = ScannedFile(
                    relative_path=rel_path,
                    size_bytes=size_bytes,
                    extension=ext,
                    decision=Decision.INCLUDE,
                    reason=Reason.INCLUDED,
                    is_symlink=is_symlink,
                    language_hint=lang_hint,
                )
                all_files.append(scanned)
                selected_files.append(scanned)

        # Recurse into valid subdirectories
        for subdir in subdirs_to_visit:
            _walk_dir(subdir)

    _walk_dir(resolved_root)

    # Sort deterministically by relative path
    all_files.sort(key=lambda f: f.relative_path)
    selected_files.sort(key=lambda f: f.relative_path)

    # Aggregate statistics
    files_excluded = sum(1 for f in all_files if f.decision == Decision.EXCLUDE)
    sensitive_detected = sum(1 for f in all_files if f.decision == Decision.SENSITIVE)
    binary_skipped = sum(1 for f in all_files if f.reason == Reason.BINARY_FILE)
    oversized_skipped = sum(1 for f in all_files if f.reason == Reason.FILE_TOO_LARGE)
    symlinks_skipped = sum(
        1
        for f in all_files
        if f.reason
        in (
            Reason.SYMLINK,
            Reason.BROKEN_SYMLINK,
            Reason.OUTSIDE_ROOT,
            Reason.SYMLINK_LOOP,
        )
    )

    return ScanSummary(
        root=str(resolved_root),
        files_seen=len(all_files),
        files_selected=len(selected_files),
        files_excluded=files_excluded,
        sensitive_files_detected=sensitive_detected,
        binary_files_skipped=binary_skipped,
        oversized_files_skipped=oversized_skipped,
        symlinks_skipped=symlinks_skipped,
        warnings=warnings,
        selected_files=selected_files,
        all_files=all_files,
    )
