"""Single-writer markdown indexing workflow."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from obsidian_memory_mcp.config import GuardrailEvaluator, ProjectConfig
from obsidian_memory_mcp.parser import PARSER_VERSION, ParsedNote, parse_markdown_bytes
from obsidian_memory_mcp.schema import bootstrap_schema, connect_index_db

DEFAULT_EXCLUDED_DIRS = frozenset({".git", ".obsidian", ".trash", ".mcp"})
SKIPPABLE_ERROR_TYPES = frozenset({"frontmatter_parse_error"})


class IndexMode(StrEnum):
    INCREMENTAL = "incremental"
    FULL = "full"


@dataclass(frozen=True)
class IndexRunResult:
    index_run_id: int
    mode: str
    status: str
    files_seen: int
    files_processed: int
    files_skipped: int
    files_deleted: int
    files_failed: int
    sections_indexed: int
    blocks_indexed: int
    errors: int
    duration_ms: int


@dataclass(frozen=True)
class FileCandidate:
    vault_path: str
    absolute_path: Path
    size_bytes: int
    mtime_ns: int


@dataclass
class _RunStats:
    files_seen: int = 0
    files_processed: int = 0
    files_skipped: int = 0
    files_deleted: int = 0
    files_failed: int = 0
    sections_indexed: int = 0
    blocks_indexed: int = 0
    errors: int = 0


@dataclass(frozen=True)
class _FileIndexError:
    error_type: str
    message: str


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
    connection: sqlite3.Connection | None = None

    try:
        connection = connect_index_db(config.index_db_location)
        bootstrap_schema(connection)
        run_id = _insert_run(connection, normalized_mode.value, parser_version)
        candidates = discover_markdown_files(config)
        file_rows = _fetch_files_by_path(connection)
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
        duration_ms = _duration_ms(started)
        _finish_run(connection, run_id, status, stats, duration_ms)
        return _result(run_id, normalized_mode.value, status, stats, duration_ms)
    except Exception as error:
        stats.errors += 1
        status = "failed"
        duration_ms = _duration_ms(started)
        if run_id > 0 and connection is not None:
            try:
                _record_error(
                    connection,
                    run_id=run_id,
                    file_id=None,
                    vault_path=None,
                    error_type=type(error).__name__,
                    message=str(error),
                )
                _finish_run(connection, run_id, status, stats, duration_ms)
            except sqlite3.Error:
                pass
        return _result(run_id, normalized_mode.value, status, stats, duration_ms)
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
    connection: sqlite3.Connection,
    run_id: int,
    candidates: tuple[FileCandidate, ...],
    file_rows: dict[str, sqlite3.Row],
    stats: _RunStats,
) -> None:
    candidate_paths = {candidate.vault_path for candidate in candidates}
    indexed_paths = {
        vault_path
        for vault_path, row in file_rows.items()
        if row["deleted_at"] is None
    }
    for vault_path in sorted(indexed_paths.difference(candidate_paths)):
        _tombstone_file(connection, run_id, vault_path)
        stats.files_deleted += 1


def _process_candidate(
    connection: sqlite3.Connection,
    run_id: int,
    candidate: FileCandidate,
    existing_file: sqlite3.Row | None,
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
        _record_file_failure(
            connection,
            candidate,
            run_id,
            parser_version=parser_version,
            file_hash=existing_file["file_hash"] if existing_file else None,
            raw_content_hash=existing_file["raw_content_hash"] if existing_file else None,
            normalized_content_hash=(
                existing_file["normalized_content_hash"] if existing_file else None
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
        and existing_file["parser_version"] == parser_version
        and existing_file["file_hash"] == file_hash
        and _can_skip_existing_error(existing_file)
    ):
        _update_metadata_for_unchanged_file(connection, existing_file["id"], candidate, run_id)
        stats.files_skipped += 1
        return

    try:
        parsed = parse_markdown_bytes(
            vault_path=candidate.vault_path,
            content=raw_bytes,
            parser_version=parser_version,
        )
    except (UnicodeDecodeError, ValueError) as error:
        _record_file_failure(
            connection,
            candidate,
            run_id,
            parser_version=parser_version,
            file_hash=file_hash,
            raw_content_hash=file_hash,
            normalized_content_hash=(
                existing_file["normalized_content_hash"] if existing_file else None
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
    _replace_file_index(connection, run_id, candidate, parsed, file_error=file_error)
    stats.files_processed += 1
    stats.sections_indexed += len(parsed.sections)
    stats.blocks_indexed += len(parsed.blocks)

    if file_error:
        stats.errors += 1


def _replace_file_index(
    connection: sqlite3.Connection,
    run_id: int,
    candidate: FileCandidate,
    parsed: ParsedNote,
    *,
    file_error: _FileIndexError | None = None,
) -> int:
    with connection:
        file_id = _upsert_file_metadata(
            connection,
            candidate,
            run_id,
            parser_version=parsed.parser_version,
            file_hash=parsed.raw_content_hash,
            raw_content_hash=parsed.raw_content_hash,
            normalized_content_hash=parsed.normalized_content_hash,
            clear_error=True,
        )
        _delete_derived_rows(connection, file_id)

        section_ids: dict[str, int] = {}
        for section in parsed.sections:
            cursor = connection.execute(
                """
                INSERT INTO sections (
                    file_id, vault_path, section_key, section_path, heading, heading_slug,
                    heading_ordinal, level, content_hash, start_line, end_line
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id,
                    section.vault_path,
                    section.section_key,
                    section.section_path,
                    section.heading,
                    section.heading_slug,
                    section.heading_ordinal,
                    section.level,
                    section.content_hash,
                    section.start_line,
                    section.end_line,
                ),
            )
            section_ids[section.section_key] = int(cursor.lastrowid)

        for block in parsed.blocks:
            section_id = section_ids[block.section_key]
            tags_json = json.dumps(list(block.tags), separators=(",", ":"))
            connection.execute(
                """
                INSERT INTO blocks (
                    file_id, section_id, vault_path, section_key, section_path, block_key,
                    heading, content, content_hash, token_count_estimate, ordinal, tags
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id,
                    section_id,
                    block.vault_path,
                    block.section_key,
                    block.section_path,
                    block.block_key,
                    block.heading,
                    block.content,
                    block.content_hash,
                    block.token_count_estimate,
                    block.ordinal,
                    tags_json,
                ),
            )
            connection.execute(
                """
                INSERT INTO blocks_fts (
                    block_key, vault_path, section_path, heading, content, tags
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    block.block_key,
                    block.vault_path,
                    block.section_path,
                    block.heading or "",
                    block.content,
                    " ".join(block.tags),
                ),
            )

        for wikilink in parsed.wikilinks:
            section_id = section_ids[wikilink.source_section_key]
            connection.execute(
                """
                INSERT INTO wikilinks (
                    file_id, section_id, vault_path, section_key, target, alias, raw
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id,
                    section_id,
                    wikilink.vault_path,
                    wikilink.source_section_key,
                    wikilink.target,
                    wikilink.alias,
                    wikilink.raw,
                ),
            )

        if file_error is not None:
            error_id = _insert_error(
                connection,
                run_id=run_id,
                file_id=file_id,
                vault_path=candidate.vault_path,
                error_type=file_error.error_type,
                message=file_error.message,
            )
            _set_file_error(connection, file_id, error_id)

    return file_id


def _upsert_file_metadata(
    connection: sqlite3.Connection,
    candidate: FileCandidate,
    run_id: int,
    *,
    parser_version: str,
    file_hash: str | None,
    raw_content_hash: str | None,
    normalized_content_hash: str | None,
    clear_error: bool,
) -> int:
    last_error_sql = "NULL" if clear_error else "last_error_id"
    connection.execute(
        f"""
        INSERT INTO files (
            vault_path, size_bytes, mtime_ns, file_hash, raw_content_hash,
            normalized_content_hash, parser_version, indexed_at, deleted_at,
            last_run_id, last_error_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL)
        ON CONFLICT(vault_path) DO UPDATE SET
            size_bytes = excluded.size_bytes,
            mtime_ns = excluded.mtime_ns,
            file_hash = excluded.file_hash,
            raw_content_hash = excluded.raw_content_hash,
            normalized_content_hash = excluded.normalized_content_hash,
            parser_version = excluded.parser_version,
            indexed_at = excluded.indexed_at,
            deleted_at = NULL,
            last_run_id = excluded.last_run_id,
            last_error_id = {last_error_sql}
        """,
        (
            candidate.vault_path,
            candidate.size_bytes,
            candidate.mtime_ns,
            file_hash,
            raw_content_hash,
            normalized_content_hash,
            parser_version,
            _now_iso(),
            run_id,
        ),
    )
    row = _fetch_file(connection, candidate.vault_path)
    if row is None:
        raise RuntimeError(f"Failed to upsert file row for {candidate.vault_path}.")
    return int(row["id"])


def _record_file_failure(
    connection: sqlite3.Connection,
    candidate: FileCandidate,
    run_id: int,
    *,
    parser_version: str,
    file_hash: str | None,
    raw_content_hash: str | None,
    normalized_content_hash: str | None,
    error_type: str,
    message: str,
) -> int:
    with connection:
        file_id = _upsert_file_metadata(
            connection,
            candidate,
            run_id,
            parser_version=parser_version,
            file_hash=file_hash,
            raw_content_hash=raw_content_hash,
            normalized_content_hash=normalized_content_hash,
            clear_error=False,
        )
        error_id = _insert_error(
            connection,
            run_id=run_id,
            file_id=file_id,
            vault_path=candidate.vault_path,
            error_type=error_type,
            message=message,
        )
        _set_file_error(connection, file_id, error_id)
    return file_id


def _update_metadata_for_unchanged_file(
    connection: sqlite3.Connection,
    file_id: int,
    candidate: FileCandidate,
    run_id: int,
) -> None:
    with connection:
        connection.execute(
            """
            UPDATE files
            SET size_bytes = ?, mtime_ns = ?, indexed_at = ?, deleted_at = NULL, last_run_id = ?
            WHERE id = ?
            """,
            (candidate.size_bytes, candidate.mtime_ns, _now_iso(), run_id, file_id),
        )


def _tombstone_file(connection: sqlite3.Connection, run_id: int, vault_path: str) -> None:
    row = _fetch_file(connection, vault_path)
    if row is None:
        return
    with connection:
        _delete_derived_rows(connection, int(row["id"]))
        connection.execute(
            """
            UPDATE files
            SET deleted_at = ?, indexed_at = ?, last_run_id = ?
            WHERE id = ?
            """,
            (_now_iso(), _now_iso(), run_id, int(row["id"])),
        )


def _delete_derived_rows(connection: sqlite3.Connection, file_id: int) -> None:
    block_keys = [
        row["block_key"]
        for row in connection.execute("SELECT block_key FROM blocks WHERE file_id = ?", (file_id,))
    ]
    connection.executemany(
        "DELETE FROM blocks_fts WHERE block_key = ?",
        ((block_key,) for block_key in block_keys),
    )
    connection.execute("DELETE FROM wikilinks WHERE file_id = ?", (file_id,))
    connection.execute("DELETE FROM blocks WHERE file_id = ?", (file_id,))
    connection.execute("DELETE FROM sections WHERE file_id = ?", (file_id,))


def _record_error(
    connection: sqlite3.Connection,
    *,
    run_id: int,
    file_id: int | None,
    vault_path: str | None,
    error_type: str,
    message: str,
) -> int:
    with connection:
        return _insert_error(
            connection,
            run_id=run_id,
            file_id=file_id,
            vault_path=vault_path,
            error_type=error_type,
            message=message,
        )


def _insert_error(
    connection: sqlite3.Connection,
    *,
    run_id: int,
    file_id: int | None,
    vault_path: str | None,
    error_type: str,
    message: str,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO index_errors (run_id, file_id, vault_path, error_type, message, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (run_id, file_id, vault_path, error_type, message, _now_iso()),
    )
    return int(cursor.lastrowid)


def _set_file_error(connection: sqlite3.Connection, file_id: int, error_id: int) -> None:
    connection.execute("UPDATE files SET last_error_id = ? WHERE id = ?", (error_id, file_id))


def _fetch_file(connection: sqlite3.Connection, vault_path: str) -> sqlite3.Row | None:
    return connection.execute("SELECT * FROM files WHERE vault_path = ?", (vault_path,)).fetchone()


def _fetch_files_by_path(connection: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    return {
        row["vault_path"]: row
        for row in connection.execute(
            """
            SELECT files.*, index_errors.error_type AS last_error_type
            FROM files
            LEFT JOIN index_errors ON index_errors.id = files.last_error_id
            """
        )
    }


def _is_stat_fresh(
    row: sqlite3.Row | None,
    candidate: FileCandidate,
    parser_version: str,
) -> bool:
    return bool(
        row is not None
        and row["deleted_at"] is None
        and row["vault_path"] == candidate.vault_path
        and row["size_bytes"] == candidate.size_bytes
        and row["mtime_ns"] == candidate.mtime_ns
        and row["parser_version"] == parser_version
        and _can_skip_existing_error(row)
    )


def _can_skip_existing_error(row: sqlite3.Row) -> bool:
    if row["last_error_id"] is None:
        return True
    return _last_error_type(row) in SKIPPABLE_ERROR_TYPES


def _last_error_type(row: sqlite3.Row) -> str | None:
    try:
        return row["last_error_type"]
    except (IndexError, KeyError):
        return None


def _insert_run(connection: sqlite3.Connection, mode: str, parser_version: str) -> int:
    with connection:
        cursor = connection.execute(
            """
            INSERT INTO index_runs (mode, status, started_at, parser_version)
            VALUES (?, 'running', ?, ?)
            """,
            (mode, _now_iso(), parser_version),
        )
    return int(cursor.lastrowid)


def _finish_run(
    connection: sqlite3.Connection,
    run_id: int,
    status: str,
    stats: _RunStats,
    duration_ms: int,
) -> None:
    with connection:
        connection.execute(
            """
            UPDATE index_runs
            SET status = ?, finished_at = ?, files_seen = ?, files_processed = ?,
                files_skipped = ?, files_deleted = ?, files_failed = ?,
                sections_indexed = ?, blocks_indexed = ?, errors = ?, duration_ms = ?
            WHERE id = ?
            """,
            (
                status,
                _now_iso(),
                stats.files_seen,
                stats.files_processed,
                stats.files_skipped,
                stats.files_deleted,
                stats.files_failed,
                stats.sections_indexed,
                stats.blocks_indexed,
                stats.errors,
                duration_ms,
                run_id,
            ),
        )


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
                        if entry.name not in DEFAULT_EXCLUDED_DIRS and not entry.is_symlink():
                            child_directories.append(
                                (entry.path, _join_relative(relative_directory, entry.name))
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


def _duration_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
