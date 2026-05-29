"""Indexed search retrieval service."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from obsidian_memory_mcp.config import ProjectConfig
from obsidian_memory_mcp.utils import glob_matches, normalize_glob
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error
from obsidian_memory_mcp.database import connect_index_db
from obsidian_memory_mcp.retrieval._preview import format_preview
from obsidian_memory_mcp.retrieval._regex import (
    RegexQuery,
    parse_regex_query,
    query_terms,
    validate_limit,
)

class SearchService:
    """Run ranked FTS5 retrieval over the Phase 2 index."""

    def __init__(self, config: ProjectConfig):
        self._config = config

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        tags: list[str] | None = None,
        paths: list[str] | None = None,
        exclude_paths: list[str] | None = None,
    ) -> dict[str, Any]:
        normalized_query = query.strip()
        if not normalized_query:
            raise _invalid_request("query is required")

        result_limit = validate_limit(limit)
        regex_query = parse_regex_query(normalized_query)
        rows = _fetch_search_rows(
            self._config,
            normalized_query,
            regex_query=regex_query,
            result_limit=result_limit,
            tags=tags or [],
            paths=paths or [],
            exclude_paths=exclude_paths or [],
        )
        results = [_row_to_result(row, normalized_query, regex_query) for row in rows]
        return {
            "query": query,
            "results": results,
            "returned_count": len(results),
        }


def _fetch_search_rows(
    config: ProjectConfig,
    normalized_query: str,
    *,
    regex_query: RegexQuery | None,
    result_limit: int,
    tags: list[str],
    paths: list[str],
    exclude_paths: list[str],
) -> list[sqlite3.Row]:
    fts_query = regex_query.fts_query if regex_query else normalized_query
    sql, params = _search_sql(
        fts_query,
        limit=None if regex_query else result_limit,
        tags=tags,
        paths=paths,
        exclude_paths=exclude_paths,
    )
    connection = connect_index_db(config.index_db_location)
    try:
        _register_glob_function(connection)
        rows = _execute_search(connection, sql, params, normalized_query)
    finally:
        connection.close()

    if regex_query is None:
        return rows

    return [
        row for row in rows if regex_query.pattern.search(row["content"]) is not None
    ][:result_limit]


def _search_sql(
    query: str,
    *,
    limit: int | None,
    tags: list[str],
    paths: list[str],
    exclude_paths: list[str],
) -> tuple[str, tuple[object, ...]]:
    where = ["blocks_fts MATCH ?", "files.deleted_at IS NULL"]
    params: list[object] = [query]
    _append_tag_filters(where, params, tags)
    _append_include_path_filters(where, params, paths)
    _append_exclude_path_filters(where, params, exclude_paths)
    if limit is not None:
        params.append(limit)
    limit_clause = "LIMIT ?" if limit is not None else ""
    return _search_select_sql(where, params, limit_clause)


def _append_tag_filters(
    where: list[str], params: list[object], tags: list[str]
) -> None:
    for tag in (_normalize_tag(tag) for tag in tags):
        if not tag:
            continue
        where.append("LOWER(blocks.tags) LIKE ? ESCAPE '\\'")
        params.append(f'%"{_escape_like_pattern(tag)}"%')


def _append_include_path_filters(
    where: list[str], params: list[object], paths: list[str]
) -> None:
    include_patterns = tuple(normalize_glob(path) for path in paths if path.strip())
    if not include_patterns:
        return
    where.append(
        "("
        + " OR ".join(
            "vault_path_glob_match(?, blocks.vault_path)" for _ in include_patterns
        )
        + ")"
    )
    params.extend(include_patterns)


def _append_exclude_path_filters(
    where: list[str], params: list[object], exclude_paths: list[str]
) -> None:
    for pattern in (normalize_glob(path) for path in exclude_paths if path.strip()):
        where.append("NOT vault_path_glob_match(?, blocks.vault_path)")
        params.append(pattern)


def _search_select_sql(
    where: list[str], params: list[object], limit_clause: str
) -> tuple[str, tuple[object, ...]]:
    return (
        f"""
        SELECT
            blocks.block_key,
            blocks.vault_path,
            blocks.heading,
            sections.level AS heading_level,
            blocks.content,
            bm25(blocks_fts, 0, 0, 1.0, 10.0, 1.0, 1.0) AS rank,
            blocks.tags
        FROM blocks_fts
        JOIN blocks ON blocks.block_key = blocks_fts.block_key
        JOIN files ON files.id = blocks.file_id
        JOIN sections ON sections.section_key = blocks.section_key
        WHERE {" AND ".join(where)}
        ORDER BY rank ASC, blocks.block_key ASC
        {limit_clause}
        """,
        tuple(params),
    )


def _execute_search(
    connection: sqlite3.Connection,
    sql: str,
    params: tuple[object, ...],
    query: str,
) -> list[sqlite3.Row]:
    try:
        return list(connection.execute(sql, params).fetchall())
    except sqlite3.OperationalError as error:
        if "no such table" in str(error).lower():
            raise ToolExecutionError(
                build_error(
                    ErrorCode.ERR_INTERNAL,
                    message="Search index has not been built for this project.",
                    details={
                        "suggestion": (
                            "Run the indexing workflow before calling search_notes."
                        ),
                    },
                )
            ) from error
        raise _invalid_request(f"invalid search query {query!r}: {error}") from error


def _row_to_result(
    row: sqlite3.Row,
    query: str,
    regex_query: RegexQuery | None,
) -> dict[str, Any]:
    tags = json.loads(row["tags"])
    return {
        "file_path": row["vault_path"],
        "heading": row["heading"] or "",
        "heading_level": int(row["heading_level"]),
        "preview": _preview(row, query, regex_query),
        "rank": float(row["rank"]),
        "tags": tags,
    }


def _preview(
    row: sqlite3.Row,
    query: str,
    regex_query: RegexQuery | None,
) -> str:
    if regex_query is not None:
        content = row["content"]
        match = regex_query.pattern.search(content)
        if match is not None:
            return format_preview(content, match.start(), match.end())

    haystack = "\n".join(part for part in (row["heading"], row["content"]) if part)
    for term in query_terms(query):
        match = re.search(re.escape(term), haystack, flags=re.IGNORECASE)
        if match is not None:
            return format_preview(haystack, match.start(), match.end())

    return format_preview(haystack, 0, 0)


def _normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("#").casefold()


def _register_glob_function(connection: sqlite3.Connection) -> None:
    connection.create_function("vault_path_glob_match", 2, _sqlite_glob_match)


def _sqlite_glob_match(pattern: str | None, vault_path: str | None) -> int:
    if pattern is None or vault_path is None:
        return 0
    return int(glob_matches(pattern, vault_path))


def _escape_like_pattern(value: str) -> str:
    return "".join(_escape_like_character(character) for character in value)


def _escape_like_character(character: str) -> str:
    if character in {"\\", "%", "_"}:
        return f"\\{character}"
    return character


def _invalid_request(message: str) -> ToolExecutionError:
    return ToolExecutionError(
        build_error(ErrorCode.ERR_INVALID_REQUEST, message=message)
    )
