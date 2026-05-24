"""Diagnostic FTS search over indexed retrieval blocks."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass

from obsidian_memory_mcp.config import ProjectConfig
from obsidian_memory_mcp.schema import bootstrap_schema, connect_index_db


@dataclass(frozen=True)
class DebugSearchResult:
    query: str
    block_key: str
    vault_path: str
    section_path: str
    heading: str | None
    bm25_score: float
    snippet: str
    token_count_estimate: int
    tags: tuple[str, ...]


class DebugSearchError(ValueError):
    """Raised when a debug search query cannot be parsed by SQLite FTS5."""


def debug_search(
    config: ProjectConfig,
    query: str,
    *,
    limit: int = 10,
    path: str | None = None,
    tag: str | None = None,
) -> tuple[DebugSearchResult, ...]:
    connection = connect_index_db(config.index_db_location)
    try:
        bootstrap_schema(connection)
        sql, params = _query_sql(query, limit=limit, path=path, tag=tag)
        try:
            rows = connection.execute(sql, params).fetchall()
        except sqlite3.OperationalError as error:
            raise DebugSearchError(f"Invalid debug search query {query!r}: {error}") from error
        return tuple(_row_to_result(query, row) for row in rows)
    finally:
        connection.close()


def search_results_to_json(query: str, results: tuple[DebugSearchResult, ...]) -> str:
    return json.dumps(
        {
            "query": query,
            "results": [
                {
                    **asdict(result),
                    "tags": list(result.tags),
                }
                for result in results
            ],
        },
        indent=2,
        sort_keys=True,
    )


def _query_sql(
    query: str,
    *,
    limit: int,
    path: str | None,
    tag: str | None,
) -> tuple[str, tuple[object, ...]]:
    where = ["blocks_fts MATCH ?", "files.deleted_at IS NULL"]
    params: list[object] = [query]
    if path:
        normalized_path = path.replace("\\", "/").lstrip("/")
        where.append("blocks.vault_path LIKE ? ESCAPE '\\'")
        params.append(f"{_escape_like_pattern(normalized_path)}%")
    if tag:
        where.append("blocks.tags LIKE ? ESCAPE '\\'")
        params.append(f'%"{_escape_like_pattern(tag.lstrip("#"))}"%')
    params.append(limit)
    return (
        f"""
        SELECT
            blocks_fts.block_key,
            blocks.vault_path,
            blocks.section_path,
            blocks.heading,
            bm25(blocks_fts) AS bm25_score,
            snippet(blocks_fts, 4, '[', ']', '...', 12) AS snippet,
            blocks.token_count_estimate,
            blocks.tags
        FROM blocks_fts
        JOIN blocks ON blocks.block_key = blocks_fts.block_key
        JOIN files ON files.id = blocks.file_id
        WHERE {" AND ".join(where)}
        -- SQLite FTS5 negates BM25, so lower scores are more relevant.
        ORDER BY bm25_score ASC, blocks.block_key ASC
        LIMIT ?
        """,
        tuple(params),
    )


def _escape_like_pattern(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _row_to_result(query: str, row: sqlite3.Row) -> DebugSearchResult:
    return DebugSearchResult(
        query=query,
        block_key=row["block_key"],
        vault_path=row["vault_path"],
        section_path=row["section_path"],
        heading=row["heading"],
        bm25_score=float(row["bm25_score"]),
        snippet=row["snippet"],
        token_count_estimate=int(row["token_count_estimate"]),
        tags=tuple(json.loads(row["tags"])),
    )
