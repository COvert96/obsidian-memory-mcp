"""SQLAlchemy Core write helpers for the markdown index."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection, CursorResult, RowMapping

from obsidian_memory_mcp.database import (
    blocks,
    files,
    index_errors,
    index_runs,
    sections,
    wikilinks,
)
from obsidian_memory_mcp.indexing._models import (
    FileCandidate,
    _FileIndexError,
    _RunStats,
)

if TYPE_CHECKING:
    from obsidian_memory_mcp.parser import ParsedNote


def replace_file_index(
    connection: Connection,
    run_id: int,
    candidate: FileCandidate,
    parsed: ParsedNote,
    *,
    file_error: _FileIndexError | None = None,
) -> int:
    with _transaction(connection):
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
    connection: Connection,
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
    with _transaction(connection):
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
    connection: Connection,
    file_id: int,
    candidate: FileCandidate,
    run_id: int,
) -> None:
    with _transaction(connection):
        connection.execute(
            update(files)
            .where(files.c.id == file_id)
            .values(
                size_bytes=candidate.size_bytes,
                mtime_ns=candidate.mtime_ns,
                indexed_at=_now_iso(),
                deleted_at=None,
                last_run_id=run_id,
            )
        )


def tombstone_file(connection: Connection, run_id: int, vault_path: str) -> None:
    with _transaction(connection):
        row = _fetch_file(connection, vault_path)
        if row is None:
            return
        file_id = _coerce_int(row["id"])
        _delete_derived_rows(connection, file_id)
        now = _now_iso()
        connection.execute(
            update(files)
            .where(files.c.id == file_id)
            .values(deleted_at=now, indexed_at=now, last_run_id=run_id)
        )


def record_error(
    connection: Connection,
    *,
    run_id: int,
    file_id: int | None,
    vault_path: str | None,
    error_type: str,
    message: str,
) -> int:
    with _transaction(connection):
        return _insert_error(
            connection,
            run_id=run_id,
            file_id=file_id,
            vault_path=vault_path,
            error_type=error_type,
            message=message,
        )


def fetch_files_by_path(connection: Connection) -> dict[str, RowMapping]:
    statement = (
        select(files, index_errors.c.error_type.label("last_error_type"))
        .select_from(
            files.outerjoin(index_errors, index_errors.c.id == files.c.last_error_id)
        )
        .order_by(files.c.vault_path)
    )
    rows = connection.execute(statement).mappings()
    return {str(row["vault_path"]): row for row in rows}


def insert_run(connection: Connection, mode: str, parser_version: str) -> int:
    with _transaction(connection):
        result = connection.execute(
            insert(index_runs).values(
                mode=mode,
                status="running",
                started_at=_now_iso(),
                parser_version=parser_version,
            )
        )
    return _last_insert_id(result, "index run insert")


def finish_run(
    connection: Connection,
    run_id: int,
    status: str,
    stats: _RunStats,
    duration_ms: int,
) -> None:
    with _transaction(connection):
        connection.execute(
            update(index_runs)
            .where(index_runs.c.id == run_id)
            .values(
                status=status,
                finished_at=_now_iso(),
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
        )


def _insert_sections(
    connection: Connection,
    file_id: int,
    parsed: ParsedNote,
) -> dict[str, int]:
    section_ids: dict[str, int] = {}
    for section in parsed.sections:
        result = connection.execute(
            insert(sections).values(
                file_id=file_id,
                vault_path=section.vault_path,
                section_key=section.section_key,
                section_path=section.section_path,
                heading=section.heading,
                heading_slug=section.heading_slug,
                heading_ordinal=section.heading_ordinal,
                level=section.level,
                content_hash=section.content_hash,
                start_line=section.start_line,
                end_line=section.end_line,
            )
        )
        section_ids[section.section_key] = _last_insert_id(result, "section insert")
    return section_ids


def _insert_blocks(
    connection: Connection,
    file_id: int,
    section_ids: dict[str, int],
    parsed: ParsedNote,
) -> None:
    for block in parsed.blocks:
        section_id = section_ids[block.section_key]
        tags_json = json.dumps(list(block.tags), separators=(",", ":"))
        connection.execute(
            insert(blocks).values(
                file_id=file_id,
                section_id=section_id,
                vault_path=block.vault_path,
                section_key=block.section_key,
                section_path=block.section_path,
                block_key=block.block_key,
                heading=block.heading,
                content=block.content,
                content_hash=block.content_hash,
                token_count_estimate=block.token_count_estimate,
                ordinal=block.ordinal,
                tags=tags_json,
            )
        )
        # FTS5 virtual-table write stays as raw SQL text by design.
        connection.execute(
            text(
                """
                INSERT INTO blocks_fts (
                    block_key, vault_path, section_path, heading, content, tags
                )
                VALUES (:block_key, :vault_path, :section_path, :heading, :content, :tags)
                """
            ),
            {
                "block_key": block.block_key,
                "vault_path": block.vault_path,
                "section_path": block.section_path,
                "heading": block.heading or "",
                "content": block.content,
                "tags": " ".join(block.tags),
            },
        )


def _insert_wikilinks(
    connection: Connection,
    file_id: int,
    section_ids: dict[str, int],
    parsed: ParsedNote,
) -> None:
    for wikilink in parsed.wikilinks:
        section_id = section_ids[wikilink.source_section_key]
        connection.execute(
            insert(wikilinks).values(
                file_id=file_id,
                section_id=section_id,
                vault_path=wikilink.vault_path,
                section_key=wikilink.source_section_key,
                target=wikilink.target,
                alias=wikilink.alias,
                raw=wikilink.raw,
            )
        )


def _upsert_file_metadata(
    connection: Connection,
    candidate: FileCandidate,
    run_id: int,
    *,
    parser_version: str,
    file_hash: str | None,
    raw_content_hash: str | None,
    normalized_content_hash: str | None,
    clear_error: bool,
) -> int:
    update_values: dict[str, Any] = {
        "size_bytes": candidate.size_bytes,
        "mtime_ns": candidate.mtime_ns,
        "file_hash": file_hash,
        "raw_content_hash": raw_content_hash,
        "normalized_content_hash": normalized_content_hash,
        "parser_version": parser_version,
        "indexed_at": _now_iso(),
        "deleted_at": None,
        "last_run_id": run_id,
        "last_error_id": None if clear_error else files.c.last_error_id,
    }
    statement = sqlite_insert(files).values(
        vault_path=candidate.vault_path,
        size_bytes=candidate.size_bytes,
        mtime_ns=candidate.mtime_ns,
        file_hash=file_hash,
        raw_content_hash=raw_content_hash,
        normalized_content_hash=normalized_content_hash,
        parser_version=parser_version,
        indexed_at=_now_iso(),
        deleted_at=None,
        last_run_id=run_id,
        last_error_id=None,
    )
    connection.execute(
        statement.on_conflict_do_update(
            index_elements=[files.c.vault_path],
            set_=update_values,
        )
    )
    row = _fetch_file(connection, candidate.vault_path)
    if row is None:
        raise RuntimeError(f"Failed to upsert file row for {candidate.vault_path}.")
    return _coerce_int(row["id"])


def _delete_derived_rows(connection: Connection, file_id: int) -> None:
    block_key_rows = connection.execute(
        select(blocks.c.block_key).where(blocks.c.file_id == file_id)
    )
    block_keys = [str(row[0]) for row in block_key_rows]
    if block_keys:
        # FTS5 virtual-table write stays as raw SQL text by design.
        connection.execute(
            text("DELETE FROM blocks_fts WHERE block_key = :block_key"),
            [{"block_key": block_key} for block_key in block_keys],
        )
    connection.execute(delete(wikilinks).where(wikilinks.c.file_id == file_id))
    connection.execute(delete(blocks).where(blocks.c.file_id == file_id))
    connection.execute(delete(sections).where(sections.c.file_id == file_id))


def _insert_error(
    connection: Connection,
    *,
    run_id: int,
    file_id: int | None,
    vault_path: str | None,
    error_type: str,
    message: str,
) -> int:
    result = connection.execute(
        insert(index_errors).values(
            run_id=run_id,
            file_id=file_id,
            vault_path=vault_path,
            error_type=error_type,
            message=message,
            created_at=_now_iso(),
        )
    )
    return _last_insert_id(result, "index error insert")


def _set_file_error(connection: Connection, file_id: int, error_id: int) -> None:
    connection.execute(
        update(files).where(files.c.id == file_id).values(last_error_id=error_id)
    )


def _fetch_file(connection: Connection, vault_path: str) -> RowMapping | None:
    return (
        connection.execute(select(files).where(files.c.vault_path == vault_path))
        .mappings()
        .first()
    )


def _last_insert_id(result: CursorResult[object], operation: str) -> int:
    primary_key = result.inserted_primary_key
    if not primary_key or primary_key[0] is None:
        raise RuntimeError(f"SQLite did not return lastrowid for {operation}.")
    return _coerce_int(primary_key[0])


@contextmanager
def _transaction(connection: Connection) -> Iterator[None]:
    if connection.in_transaction():
        yield
        return
    with connection.begin():
        yield


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _coerce_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"Expected int-compatible value, received {type(value).__name__}.")
