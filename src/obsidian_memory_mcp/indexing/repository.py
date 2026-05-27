"""SQLite write helpers for the markdown index."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from obsidian_memory_mcp.indexing._models import (
    FileCandidate,
    _FileIndexError,
    _RunStats,
)

if TYPE_CHECKING:
    from obsidian_memory_mcp.parser import ParsedNote


def replace_file_index(
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
        section_ids = _insert_sections(connection, file_id, parsed)
        _insert_blocks(connection, file_id, section_ids, parsed)
        _insert_wikilinks(connection, file_id, section_ids, parsed)

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


def record_file_failure(
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


def update_metadata_for_unchanged_file(
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


def tombstone_file(
    connection: sqlite3.Connection, run_id: int, vault_path: str
) -> None:
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


def record_error(
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


def fetch_files_by_path(connection: sqlite3.Connection) -> dict[str, sqlite3.Row]:
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


def insert_run(connection: sqlite3.Connection, mode: str, parser_version: str) -> int:
    with connection:
        cursor = connection.execute(
            """
            INSERT INTO index_runs (mode, status, started_at, parser_version)
            VALUES (?, 'running', ?, ?)
            """,
            (mode, _now_iso(), parser_version),
        )
    return _last_insert_id(cursor, "index run insert")


def finish_run(
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


def _insert_sections(
    connection: sqlite3.Connection,
    file_id: int,
    parsed: ParsedNote,
) -> dict[str, int]:
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
        section_ids[section.section_key] = _last_insert_id(cursor, "section insert")
    return section_ids


def _insert_blocks(
    connection: sqlite3.Connection,
    file_id: int,
    section_ids: dict[str, int],
    parsed: ParsedNote,
) -> None:
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


def _insert_wikilinks(
    connection: sqlite3.Connection,
    file_id: int,
    section_ids: dict[str, int],
    parsed: ParsedNote,
) -> None:
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


def _delete_derived_rows(connection: sqlite3.Connection, file_id: int) -> None:
    block_keys = [
        row["block_key"]
        for row in connection.execute(
            "SELECT block_key FROM blocks WHERE file_id = ?", (file_id,)
        )
    ]
    connection.executemany(
        "DELETE FROM blocks_fts WHERE block_key = ?",
        ((block_key,) for block_key in block_keys),
    )
    connection.execute("DELETE FROM wikilinks WHERE file_id = ?", (file_id,))
    connection.execute("DELETE FROM blocks WHERE file_id = ?", (file_id,))
    connection.execute("DELETE FROM sections WHERE file_id = ?", (file_id,))


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
    return _last_insert_id(cursor, "index error insert")


def _set_file_error(
    connection: sqlite3.Connection, file_id: int, error_id: int
) -> None:
    connection.execute(
        "UPDATE files SET last_error_id = ? WHERE id = ?", (error_id, file_id)
    )


def _fetch_file(connection: sqlite3.Connection, vault_path: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM files WHERE vault_path = ?", (vault_path,)
    ).fetchone()


def _last_insert_id(cursor: sqlite3.Cursor, operation: str) -> int:
    if cursor.lastrowid is None:
        raise RuntimeError(f"SQLite did not return lastrowid for {operation}.")
    return cursor.lastrowid


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
