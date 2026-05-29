"""Single-writer markdown indexing workflow."""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from obsidian_memory_mcp.utils import duration_ms
from obsidian_memory_mcp.config import ProjectConfig
from obsidian_memory_mcp.database import get_connection
from obsidian_memory_mcp.indexing._candidates import (
    process_candidate,
    process_deleted_files,
)
from obsidian_memory_mcp.indexing._discovery import discover_markdown_files
from obsidian_memory_mcp.indexing._models import (
    IndexMode,
    IndexRunResult,
    _RunStats,
)
from obsidian_memory_mcp.indexing.repository import (
    fetch_files_by_path,
    finish_run,
    insert_run,
    record_error,
)
from obsidian_memory_mcp.indexing.parser import PARSER_VERSION, parse_markdown_bytes
from obsidian_memory_mcp.indexing.repository import replace_file_index
from obsidian_memory_mcp.migrations import ensure_index_migrated

LOGGER = logging.getLogger(__name__)

__all__ = [
    "parse_markdown_bytes",
    "read_file_bytes",
    "replace_file_index",
    "run_index",
]


def read_file_bytes(path: Path) -> bytes:
    return path.read_bytes()


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
        process_deleted_files(connection, run_id, candidates, file_rows, stats)
        for candidate in candidates:
            process_candidate(
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
