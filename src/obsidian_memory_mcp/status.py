"""Index health and drift reporting."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from obsidian_memory_mcp.config import ProjectConfig
from obsidian_memory_mcp.indexing import FileCandidate, discover_markdown_files
from obsidian_memory_mcp.indexing.parser import PARSER_VERSION
from obsidian_memory_mcp.database import connect_index_db
from obsidian_memory_mcp.migrations import current_revision, ensure_index_migrated

_COUNTABLE_TABLES = frozenset({"sections", "blocks", "wikilinks"})


@dataclass(frozen=True)
class IndexStatus:
    vault_path: str
    index_db_path: str
    schema_revision: str | None
    parser_version: str
    last_run_time: str | None
    last_run_status: str | None
    total_markdown_files: int
    indexed_files: int
    unindexed_files: int
    changed_files: int
    deleted_indexed_files: int
    files_with_errors: int
    total_sections: int
    total_blocks: int
    total_wikilinks: int
    parser_version_drift: int
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class IndexErrorRecord:
    id: int
    run_id: int
    vault_path: str | None
    error_type: str
    message: str
    created_at: str


def get_index_status(
    config: ProjectConfig,
    *,
    parser_version: str = PARSER_VERSION,
) -> IndexStatus:
    ensure_index_migrated(config.index_db_location)
    connection = connect_index_db(config.index_db_location)
    try:
        candidates = discover_markdown_files(config)
        candidate_by_path = {
            candidate.vault_path: candidate for candidate in candidates
        }
        file_rows = _active_file_rows(connection)
        metrics = _index_status_metrics(
            candidate_by_path,
            file_rows,
            parser_version=parser_version,
            total_markdown_files=len(candidates),
        )
        last_run = connection.execute(
            "SELECT finished_at, status FROM index_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()

        return IndexStatus(
            vault_path=str(config.vault_path),
            index_db_path=str(config.index_db_location),
            schema_revision=current_revision(config.index_db_location),
            parser_version=parser_version,
            last_run_time=last_run["finished_at"] if last_run else None,
            last_run_status=last_run["status"] if last_run else None,
            total_markdown_files=len(candidates),
            indexed_files=metrics.indexed_files,
            unindexed_files=metrics.unindexed_files,
            changed_files=metrics.changed_files,
            deleted_indexed_files=metrics.deleted_indexed_files,
            files_with_errors=metrics.files_with_errors,
            total_sections=_count(connection, "sections"),
            total_blocks=_count(connection, "blocks"),
            total_wikilinks=_count(connection, "wikilinks"),
            parser_version_drift=metrics.parser_version_drift,
            warnings=metrics.warnings,
        )
    finally:
        connection.close()


@dataclass(frozen=True)
class _IndexStatusMetrics:
    indexed_files: int
    unindexed_files: int
    changed_files: int
    deleted_indexed_files: int
    files_with_errors: int
    parser_version_drift: int
    warnings: tuple[str, ...]


def _active_file_rows(connection: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    return {
        row["vault_path"]: row
        for row in connection.execute("SELECT * FROM files WHERE deleted_at IS NULL")
    }


def _index_status_metrics(
    candidate_by_path: dict[str, FileCandidate],
    file_rows: dict[str, sqlite3.Row],
    *,
    parser_version: str,
    total_markdown_files: int,
) -> _IndexStatusMetrics:
    indexed_paths = set(file_rows)
    candidate_paths = set(candidate_by_path)
    changed_files = sum(
        1
        for vault_path in candidate_paths.intersection(indexed_paths)
        if _metadata_changed(file_rows[vault_path], candidate_by_path[vault_path])
    )
    parser_version_drift = sum(
        1 for row in file_rows.values() if row["parser_version"] != parser_version
    )
    files_with_errors = sum(
        1 for row in file_rows.values() if row["last_error_id"] is not None
    )
    return _IndexStatusMetrics(
        indexed_files=len(indexed_paths),
        unindexed_files=len(candidate_paths.difference(indexed_paths)),
        changed_files=changed_files,
        deleted_indexed_files=len(indexed_paths.difference(candidate_paths)),
        files_with_errors=files_with_errors,
        parser_version_drift=parser_version_drift,
        warnings=_warnings(
            files_with_errors=files_with_errors,
            total_markdown_files=total_markdown_files,
            parser_version_drift=parser_version_drift,
        ),
    )


def list_index_errors(
    config: ProjectConfig, *, limit: int = 50
) -> tuple[IndexErrorRecord, ...]:
    ensure_index_migrated(config.index_db_location)
    connection = connect_index_db(config.index_db_location)
    try:
        rows = connection.execute(
            """
            SELECT id, run_id, vault_path, error_type, message, created_at
            FROM index_errors
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return tuple(
            IndexErrorRecord(
                id=int(row["id"]),
                run_id=int(row["run_id"]),
                vault_path=row["vault_path"],
                error_type=row["error_type"],
                message=row["message"],
                created_at=row["created_at"],
            )
            for row in rows
        )
    finally:
        connection.close()


def _metadata_changed(row: sqlite3.Row, candidate: FileCandidate) -> bool:
    return bool(
        row["size_bytes"] != candidate.size_bytes
        or row["mtime_ns"] != candidate.mtime_ns
    )


def _count(connection: sqlite3.Connection, table: str) -> int:
    if table not in _COUNTABLE_TABLES:
        raise ValueError(f"Invalid count table: {table!r}")
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _warnings(
    *,
    files_with_errors: int,
    total_markdown_files: int,
    parser_version_drift: int,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if total_markdown_files and files_with_errors / total_markdown_files > 0.10:
        warnings.append(">10% of eligible files currently have indexing errors.")
    if parser_version_drift:
        warnings.append("Parser version drift exists.")
    return tuple(warnings)
