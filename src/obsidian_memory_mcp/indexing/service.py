"""Single-writer markdown indexing workflow."""

from __future__ import annotations

import hashlib
import logging
import os
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from obsidian_memory_mcp._time import duration_ms
from obsidian_memory_mcp.config import GuardrailEvaluator, ProjectConfig
from obsidian_memory_mcp.database import get_connection
from obsidian_memory_mcp.indexing._models import (
    FileCandidate,
    IndexMode,
    IndexRunResult,
    _FileIndexError,
    _RunStats,
)
from obsidian_memory_mcp.indexing.repository import (
    fetch_files_by_path,
    finish_run,
    insert_run,
    record_error,
    record_file_failure,
    replace_file_index,
    tombstone_file,
    update_metadata_for_unchanged_file,
)
from obsidian_memory_mcp.parser import PARSER_VERSION, parse_markdown_bytes
from obsidian_memory_mcp.migrations import ensure_index_migrated

DEFAULT_EXCLUDED_DIRS = frozenset({".git", ".obsidian", ".trash", ".mcp"})
SKIPPABLE_ERROR_TYPES = frozenset({"frontmatter_parse_error"})
LOGGER = logging.getLogger(__name__)


def run_index(
    config: ProjectConfig,
    *,
    mode: IndexMode | str = IndexMode.INCREMENTAL,
    parser_version: str = PARSER_VERSION,
) -> IndexRunResult:
    started = time.perf_counter()
    normalized_mode = IndexMode(mode)
    stats = _RunStats()
    run_id = -1
    connection = None

    try:
        ensure_index_migrated(config.index_db_location)
        connection = get_connection(config.index_db_location)
        run_id = insert_run(connection, normalized_mode.value, parser_version)
        candidates = discover_markdown_files(config)
        file_rows = cast(
            dict[str, Mapping[str, object]], fetch_files_by_path(connection)
        )
        connection.commit()
        stats.files_seen = len(candidates)
        _process_deleted_files(connection, run_id, candidates, file_rows, stats)
        for candidate in candidates:
            _process_candidate(
                connection,
                run_id,
                candidate,
                file_rows.get(candidate.vault_path),
                stats,
                parser_version=parser_version,
                force_reindex=normalized_mode is IndexMode.FULL,
            )
        status = _status_for(stats)
        elapsed = duration_ms(started)
        finish_run(connection, run_id, status, stats, elapsed)
        return _result(run_id, normalized_mode.value, status, stats, elapsed)
    except Exception as error:
        stats.errors += 1
        status = "failed"
        elapsed = duration_ms(started)
        if run_id > 0 and connection is not None:
            try:
                record_error(
                    connection,
                    run_id=run_id,
                    file_id=None,
                    vault_path=None,
                    error_type=type(error).__name__,
                    message=str(error),
                )
                finish_run(connection, run_id, status, stats, elapsed)
            except Exception:
                LOGGER.exception("Failed to persist index failure diagnostics.")
        return _result(run_id, normalized_mode.value, status, stats, elapsed)
    finally:
        if connection is not None:
            connection.close()


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


def read_file_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _process_deleted_files(
    connection: Any,
    run_id: int,
    candidates: tuple[FileCandidate, ...],
    file_rows: dict[str, Mapping[str, object]],
    stats: _RunStats,
) -> None:
    candidate_paths = {candidate.vault_path for candidate in candidates}
    indexed_paths = {
        vault_path for vault_path, row in file_rows.items() if row["deleted_at"] is None
    }
    for vault_path in sorted(indexed_paths.difference(candidate_paths)):
        tombstone_file(connection, run_id, vault_path)
        stats.files_deleted += 1


def _process_candidate(
    connection: Any,
    run_id: int,
    candidate: FileCandidate,
    existing_file: Mapping[str, object] | None,
    stats: _RunStats,
    *,
    parser_version: str,
    force_reindex: bool,
) -> None:
    if not force_reindex and _is_stat_fresh(existing_file, candidate, parser_version):
        stats.files_skipped += 1
        return

    try:
        raw_bytes = read_file_bytes(candidate.absolute_path)
    except OSError as error:
        record_file_failure(
            connection,
            candidate,
            run_id,
            parser_version=parser_version,
            file_hash=_row_optional_str(existing_file, "file_hash"),
            raw_content_hash=_row_optional_str(existing_file, "raw_content_hash"),
            normalized_content_hash=(
                _row_optional_str(existing_file, "normalized_content_hash")
            ),
            error_type=type(error).__name__,
            message=str(error),
        )
        stats.files_failed += 1
        stats.errors += 1
        return

    file_hash = _sha256(raw_bytes)
    if (
        not force_reindex
        and existing_file is not None
        and existing_file["deleted_at"] is None
        and str(existing_file["parser_version"]) == parser_version
        and _row_optional_str(existing_file, "file_hash") == file_hash
        and _can_skip_existing_error(existing_file)
    ):
        update_metadata_for_unchanged_file(
            connection, _row_int(existing_file, "id"), candidate, run_id
        )
        stats.files_skipped += 1
        return

    try:
        parsed = parse_markdown_bytes(
            vault_path=candidate.vault_path,
            content=raw_bytes,
            parser_version=parser_version,
        )
    except (UnicodeDecodeError, ValueError) as error:
        record_file_failure(
            connection,
            candidate,
            run_id,
            parser_version=parser_version,
            file_hash=file_hash,
            raw_content_hash=file_hash,
            normalized_content_hash=(
                _row_optional_str(existing_file, "normalized_content_hash")
            ),
            error_type=type(error).__name__,
            message=str(error),
        )
        stats.files_failed += 1
        stats.errors += 1
        return

    file_error = (
        _FileIndexError(
            error_type="frontmatter_parse_error",
            message=f"{candidate.vault_path} contains malformed YAML frontmatter.",
        )
        if parsed.frontmatter_parse_error
        else None
    )
    replace_file_index(connection, run_id, candidate, parsed, file_error=file_error)
    stats.files_processed += 1
    stats.sections_indexed += len(parsed.sections)
    stats.blocks_indexed += len(parsed.blocks)

    if file_error:
        stats.errors += 1


def _is_stat_fresh(
    row: Mapping[str, object] | None,
    candidate: FileCandidate,
    parser_version: str,
) -> bool:
    return bool(
        row is not None
        and row["deleted_at"] is None
        and str(row["vault_path"]) == candidate.vault_path
        and _row_int(row, "size_bytes") == candidate.size_bytes
        and _row_int(row, "mtime_ns") == candidate.mtime_ns
        and str(row["parser_version"]) == parser_version
        and _can_skip_existing_error(row)
    )


def _can_skip_existing_error(row: Mapping[str, object]) -> bool:
    if row["last_error_id"] is None:
        return True
    return _last_error_type(row) in SKIPPABLE_ERROR_TYPES


def _last_error_type(row: Mapping[str, object]) -> str | None:
    try:
        value = row["last_error_type"]
        return str(value) if value is not None else None
    except (IndexError, KeyError):
        return None


def _row_int(row: Mapping[str, object], field: str) -> int:
    return _coerce_int(row[field])


def _row_optional_str(row: Mapping[str, object] | None, field: str) -> str | None:
    if row is None:
        return None
    value = row[field]
    return str(value) if value is not None else None


def _status_for(stats: _RunStats) -> str:
    if stats.files_failed or stats.errors:
        return "success_with_errors"
    return "success"


def _result(
    run_id: int,
    mode: str,
    status: str,
    stats: _RunStats,
    duration_ms: int,
) -> IndexRunResult:
    return IndexRunResult(
        index_run_id=run_id,
        mode=mode,
        status=status,
        files_seen=stats.files_seen,
        files_processed=stats.files_processed,
        files_skipped=stats.files_skipped,
        files_deleted=stats.files_deleted,
        files_failed=stats.files_failed,
        sections_indexed=stats.sections_indexed,
        blocks_indexed=stats.blocks_indexed,
        errors=stats.errors,
        duration_ms=duration_ms,
    )


def _is_excluded(path: str, index_db_path: str) -> bool:
    return os.path.normcase(os.path.abspath(path)) == index_db_path


def _iter_markdown_entries(
    vault_root: Path,
) -> tuple[tuple[str, os.DirEntry[str]], ...]:
    found: list[tuple[str, os.DirEntry[str]]] = []
    stack: list[tuple[str, str]] = [(str(vault_root), "")]

    while stack:
        directory, relative_directory = stack.pop()
        child_directories: list[tuple[str, str]] = []
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if entry.is_dir(follow_symlinks=False):
                        if (
                            entry.name not in DEFAULT_EXCLUDED_DIRS
                            and not entry.is_symlink()
                        ):
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
                        found.append(
                            (_join_relative(relative_directory, entry.name), entry)
                        )
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


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _coerce_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"Expected int-compatible value, received {type(value).__name__}.")
