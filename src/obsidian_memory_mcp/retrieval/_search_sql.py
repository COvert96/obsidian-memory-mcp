"""SQLite FTS5 query construction and execution for indexed search."""

from __future__ import annotations

import sqlite3

from obsidian_memory_mcp.utils import glob_matches, normalize_glob
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error


def search_sql(
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


def execute_search(
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
        raise invalid_search_request(
            f"invalid search query {query!r}: {error}"
        ) from error


def register_glob_function(connection: sqlite3.Connection) -> None:
    connection.create_function("vault_path_glob_match", 2, _sqlite_glob_match)


def invalid_search_request(message: str) -> ToolExecutionError:
    return ToolExecutionError(
        build_error(ErrorCode.ERR_INVALID_REQUEST, message=message)
    )


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


def _normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("#").casefold()


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
