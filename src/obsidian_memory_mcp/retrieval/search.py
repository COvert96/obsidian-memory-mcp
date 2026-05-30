"""Indexed search retrieval service."""

from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from obsidian_memory_mcp.config import ProjectConfig
from obsidian_memory_mcp.database import connect_index_db
from obsidian_memory_mcp.retrieval._preview import format_preview
from obsidian_memory_mcp.retrieval._fts_query import prepare_fts_match_query
from obsidian_memory_mcp.retrieval._regex import (
    RegexQuery,
    parse_regex_query,
    query_terms,
    validate_limit,
)
from obsidian_memory_mcp.retrieval._search_sql import (
    execute_search,
    invalid_search_request,
    register_glob_function,
    search_sql,
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
            raise invalid_search_request("query is required")

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
    fts_query = (
        regex_query.fts_query
        if regex_query
        else prepare_fts_match_query(normalized_query)
    )
    sql, params = search_sql(
        fts_query,
        limit=None if regex_query else result_limit,
        tags=tags,
        paths=paths,
        exclude_paths=exclude_paths,
    )
    connection = connect_index_db(config.index_db_location)
    try:
        register_glob_function(connection)
        rows = execute_search(connection, sql, params, normalized_query)
    finally:
        connection.close()

    if regex_query is None:
        return rows

    return [
        row for row in rows if regex_query.pattern.search(row["content"]) is not None
    ][:result_limit]


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
