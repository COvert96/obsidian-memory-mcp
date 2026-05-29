"""Markdown file discovery for indexing.

Kept separate from `indexing.service` so indexing orchestration remains easier to scan.
"""

from __future__ import annotations

import os
from pathlib import Path

from obsidian_memory_mcp.config import GuardrailEvaluator, ProjectConfig
from obsidian_memory_mcp.indexing._models import FileCandidate

DEFAULT_EXCLUDED_DIRS = frozenset({".git", ".obsidian", ".trash", ".mcp"})


def discover_markdown_files(config: ProjectConfig) -> tuple[FileCandidate, ...]:
    vault_root = config.vault_path.resolve(strict=True)
    index_db_path = os.path.normcase(os.path.abspath(config.index_db_location))
    guardrails = GuardrailEvaluator(config)
    candidates: list[FileCandidate] = []

    for relative_path, entry in _iter_markdown_entries(vault_root):
        if _is_excluded(entry.path, index_db_path):
            continue

        if not guardrails.allows_read_relative(relative_path):
            continue

        try:
            real_path, stat = _candidate_path_and_stat(entry, vault_root)
        except OSError:
            continue

        candidates.append(
            FileCandidate(
                vault_path=relative_path,
                absolute_path=real_path,
                size_bytes=stat.st_size,
                mtime_ns=stat.st_mtime_ns,
            )
        )

    return tuple(candidates)


def _is_excluded(path: str, index_db_path: str) -> bool:
    return os.path.normcase(os.path.abspath(path)) == index_db_path


def _iter_markdown_entries(
    vault_root: Path,
) -> tuple[tuple[str, os.DirEntry[str]], ...]:
    """Return a stable ordering of markdown file entries under the vault.

    This intentionally uses `os.scandir` + a manual stack to avoid recursion depth
    hazards and to keep ordering deterministic across platforms.
    """

    found: list[tuple[str, os.DirEntry[str]]] = []
    stack: list[tuple[str, str]] = [(str(vault_root), "")]

    while stack:
        directory, relative_directory = stack.pop()
        child_directories: list[tuple[str, str]] = []
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in DEFAULT_EXCLUDED_DIRS and not entry.is_symlink():
                            child_directories.append(
                                (
                                    entry.path,
                                    _join_relative(relative_directory, entry.name),
                                )
                            )
                        continue
                    if entry.name.endswith(".md") and (
                        entry.is_file(follow_symlinks=False) or entry.is_symlink()
                    ):
                        found.append((_join_relative(relative_directory, entry.name), entry))
        except OSError:
            continue

        stack.extend(
            sorted(child_directories, key=lambda item: item[1].lower(), reverse=True)
        )

    return tuple(sorted(found, key=lambda item: item[0].lower()))


def _candidate_path_and_stat(
    entry: os.DirEntry[str],
    vault_root: Path,
) -> tuple[Path, os.stat_result]:
    path = Path(entry.path)
    if entry.is_symlink():
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(vault_root):
            raise OSError(f"Symlink target escapes vault root: {path}")
        return resolved, resolved.stat()
    return path, entry.stat(follow_symlinks=False)


def _join_relative(parent: str, child: str) -> str:
    if not parent:
        return child
    return f"{parent}/{child}"

