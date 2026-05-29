"""Per-file indexing pipeline helpers used by ``indexing.service``."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import obsidian_memory_mcp.indexing.service as indexing_service

from obsidian_memory_mcp.indexing._models import FileCandidate, _FileIndexError, _RunStats
from obsidian_memory_mcp.indexing.repository import (
    record_file_failure,
    tombstone_file,
    update_metadata_for_unchanged_file,
)

SKIPPABLE_ERROR_TYPES = frozenset({"frontmatter_parse_error"})


def process_deleted_files(
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


def process_candidate(
    connection: Any,
    run_id: int,
    candidate: FileCandidate,
    existing_file: Mapping[str, object] | None,
    stats: _RunStats,
    *,
    parser_version: str,
    force_reindex: bool,
) -> None:
    if skip_fresh_candidate(
        existing_file, candidate, parser_version, force_reindex=force_reindex
    ):
        stats.files_skipped += 1
        return

    raw_bytes = read_candidate_bytes(
        connection,
        candidate,
        existing_file,
        run_id,
        parser_version=parser_version,
        stats=stats,
    )
    if raw_bytes is None:
        return

    file_hash = sha256_bytes(raw_bytes)
    if skip_unchanged_candidate(
        connection,
        candidate,
        existing_file,
        run_id,
        file_hash=file_hash,
        parser_version=parser_version,
        force_reindex=force_reindex,
        stats=stats,
    ):
        return

    index_candidate_bytes(
        connection,
        candidate,
        existing_file,
        run_id,
        raw_bytes=raw_bytes,
        file_hash=file_hash,
        parser_version=parser_version,
        stats=stats,
    )


def skip_fresh_candidate(
    existing_file: Mapping[str, object] | None,
    candidate: FileCandidate,
    parser_version: str,
    *,
    force_reindex: bool,
) -> bool:
    return not force_reindex and is_stat_fresh(
        existing_file, candidate, parser_version
    )


def read_candidate_bytes(
    connection: Any,
    candidate: FileCandidate,
    existing_file: Mapping[str, object] | None,
    run_id: int,
    *,
    parser_version: str,
    stats: _RunStats,
) -> bytes | None:
    try:
        return indexing_service.read_file_bytes(candidate.absolute_path)
    except OSError as error:
        record_file_failure(
            connection,
            candidate,
            run_id,
            parser_version=parser_version,
            file_hash=row_optional_str(existing_file, "file_hash"),
            raw_content_hash=row_optional_str(existing_file, "raw_content_hash"),
            normalized_content_hash=(
                row_optional_str(existing_file, "normalized_content_hash")
            ),
            error_type=type(error).__name__,
            message=str(error),
        )
        stats.files_failed += 1
        stats.errors += 1
        return None


def skip_unchanged_candidate(
    connection: Any,
    candidate: FileCandidate,
    existing_file: Mapping[str, object] | None,
    run_id: int,
    *,
    file_hash: str,
    parser_version: str,
    force_reindex: bool,
    stats: _RunStats,
) -> bool:
    """Skip indexing when bytes and parser version are unchanged."""
    if force_reindex or existing_file is None:
        return False
    if existing_file["deleted_at"] is not None:
        return False
    if str(existing_file["parser_version"]) != parser_version:
        return False
    if row_optional_str(existing_file, "file_hash") != file_hash:
        return False
    if not can_skip_existing_error(existing_file):
        return False

    update_metadata_for_unchanged_file(
        connection, row_int(existing_file, "id"), candidate, run_id
    )
    stats.files_skipped += 1
    return True


def index_candidate_bytes(
    connection: Any,
    candidate: FileCandidate,
    existing_file: Mapping[str, object] | None,
    run_id: int,
    *,
    raw_bytes: bytes,
    file_hash: str,
    parser_version: str,
    stats: _RunStats,
) -> None:
    try:
        parsed = indexing_service.parse_markdown_bytes(
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
                row_optional_str(existing_file, "normalized_content_hash")
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
    indexing_service.replace_file_index(
        connection, run_id, candidate, parsed, file_error=file_error
    )
    stats.files_processed += 1
    stats.sections_indexed += len(parsed.sections)
    stats.blocks_indexed += len(parsed.blocks)
    if file_error:
        stats.errors += 1


def is_stat_fresh(
    row: Mapping[str, object] | None,
    candidate: FileCandidate,
    parser_version: str,
) -> bool:
    return bool(
        row is not None
        and row["deleted_at"] is None
        and str(row["vault_path"]) == candidate.vault_path
        and row_int(row, "size_bytes") == candidate.size_bytes
        and row_int(row, "mtime_ns") == candidate.mtime_ns
        and str(row["parser_version"]) == parser_version
        and can_skip_existing_error(row)
    )


def can_skip_existing_error(row: Mapping[str, object]) -> bool:
    if row["last_error_id"] is None:
        return True
    return last_error_type(row) in SKIPPABLE_ERROR_TYPES


def last_error_type(row: Mapping[str, object]) -> str | None:
    try:
        value = row["last_error_type"]
        return str(value) if value is not None else None
    except (IndexError, KeyError):
        return None


def row_int(row: Mapping[str, object], field: str) -> int:
    return coerce_int(row[field])


def row_optional_str(row: Mapping[str, object] | None, field: str) -> str | None:
    if row is None:
        return None
    value = row[field]
    return str(value) if value is not None else None


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def coerce_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"Expected int-compatible value, received {type(value).__name__}.")
