"""Retrieval use cases for guarded note reads and indexed search."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from obsidian_memory_mcp.config import GuardrailEvaluator, ProjectConfig
from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error
from obsidian_memory_mcp.schema import connect_index_db
from obsidian_memory_mcp.vault import parse_frontmatter

_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
_FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})")
_BOOLEAN_TERMS = frozenset({"AND", "OR", "NOT"})
_MAX_SEARCH_LIMIT = 100
_PREVIEW_RADIUS = 80
_PREVIEW_MIN_LENGTH = 180
_PREVIEW_MAX_LENGTH = 200


class ReadNoteService:
    """Read complete markdown notes through the configured read guardrails."""

    def __init__(self, config: ProjectConfig, guardrails: GuardrailEvaluator):
        self._config = config
        self._guardrails = guardrails

    def read(self, note_path: str) -> dict[str, Any]:
        resolved_path = _resolve_existing_note(
            self._config, self._guardrails, note_path
        )
        raw = _read_text(self._config, resolved_path)
        return {
            "file_path": resolved_path.relative_to(self._config.vault_path).as_posix(),
            "content": raw,
            "frontmatter": parse_frontmatter(raw),
            "file_size_bytes": len(raw.encode("utf-8")),
        }


class ReadSectionService:
    """Read one heading section from a guarded markdown note."""

    def __init__(self, config: ProjectConfig, guardrails: GuardrailEvaluator):
        self._config = config
        self._guardrails = guardrails

    def read(self, note_path: str, heading_name: str) -> dict[str, Any]:
        resolved_path = _resolve_existing_note(
            self._config, self._guardrails, note_path
        )
        raw = _read_text(self._config, resolved_path)
        section = _extract_section(raw, heading_name)
        if section is None:
            file_path = resolved_path.relative_to(self._config.vault_path).as_posix()
            raise ToolExecutionError(
                build_error(
                    ErrorCode.ERR_SECTION_NOT_FOUND,
                    details={"file_path": file_path, "heading_name": heading_name},
                )
            )

        return {
            "file_path": resolved_path.relative_to(self._config.vault_path).as_posix(),
            "heading": section.heading,
            "heading_level": section.heading_level,
            "content": section.content,
            "context_prefix": section.context_prefix,
        }


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

        result_limit = _validate_limit(limit)
        regex_query = _parse_regex_query(normalized_query)
        fts_query = regex_query.fts_query if regex_query else normalized_query
        sql, params = _search_sql(
            fts_query,
            limit=None if regex_query else result_limit,
            tags=tags or [],
            paths=paths or [],
            exclude_paths=exclude_paths or [],
        )

        connection = connect_index_db(self._config.index_db_location)
        try:
            _register_glob_function(connection)
            rows = _execute_search(connection, sql, params, normalized_query)
        finally:
            connection.close()

        if regex_query is not None:
            rows = [
                row
                for row in rows
                if regex_query.pattern.search(row["content"]) is not None
            ][:result_limit]

        results = [_row_to_result(row, normalized_query, regex_query) for row in rows]
        return {
            "query": query,
            "results": results,
            "returned_count": len(results),
        }


@dataclass(frozen=True)
class _Heading:
    line_index: int
    level: int
    text: str


@dataclass(frozen=True)
class _FenceState:
    marker: str
    length: int


@dataclass(frozen=True)
class _ExtractedSection:
    heading: str
    heading_level: int
    content: str
    context_prefix: str


@dataclass(frozen=True)
class _RegexQuery:
    pattern: re.Pattern[str]
    fts_query: str


def _resolve_existing_note(
    config: ProjectConfig,
    guardrails: GuardrailEvaluator,
    note_path: str,
) -> Path:
    resolved_path = guardrails.check_read(note_path)
    if resolved_path.is_file():
        return resolved_path

    relative = resolved_path.relative_to(config.vault_path).as_posix()
    raise ToolExecutionError(
        build_error(ErrorCode.ERR_MISSING_FILE, details={"file_path": relative})
    )


def _read_text(config: ProjectConfig, path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except PermissionError as error:
        relative = path.relative_to(config.vault_path).as_posix()
        raise ToolExecutionError(
            build_error(
                ErrorCode.ERR_GUARDRAIL_VIOLATION,
                message=f"Path '{relative}' is not readable.",
                details={"path": relative, "suggestion": "Choose a readable note."},
            )
        ) from error


def _extract_section(content: str, heading_name: str) -> _ExtractedSection | None:
    lines = content.splitlines()
    headings = _find_headings(lines)
    heading = _matching_heading(headings, heading_name)
    if heading is None:
        return None

    end_index = _section_end_index(headings, heading, line_count=len(lines))
    section_content = "\n".join(lines[heading.line_index : end_index]).rstrip()
    context_prefix = _context_prefix(lines, headings, heading.line_index)
    return _ExtractedSection(
        heading=heading.text,
        heading_level=heading.level,
        content=section_content,
        context_prefix=context_prefix,
    )


def _find_headings(lines: list[str]) -> tuple[_Heading, ...]:
    headings: list[_Heading] = []
    fence_state: _FenceState | None = None

    for index, line in enumerate(lines):
        fence_match = _FENCE_RE.match(line)
        if fence_match is not None:
            fence_state = _next_fence_state(fence_match, fence_state)
            continue
        if fence_state is not None:
            continue

        match = _HEADING_RE.match(line)
        if match is None:
            continue

        headings.append(
            _Heading(
                line_index=index,
                level=len(match.group(1)),
                text=_clean_heading_text(match.group(2)),
            )
        )

    return tuple(headings)


def _matching_heading(
    headings: tuple[_Heading, ...],
    heading_name: str,
) -> _Heading | None:
    target = _normalize_heading_name(heading_name)
    return next(
        (
            heading
            for heading in headings
            if _normalize_heading_name(heading.text) == target
        ),
        None,
    )


def _section_end_index(
    headings: tuple[_Heading, ...],
    current: _Heading,
    *,
    line_count: int,
) -> int:
    following_headings = (
        heading for heading in headings if heading.line_index > current.line_index
    )
    for heading in following_headings:
        if heading.level <= current.level:
            return heading.line_index
    return line_count


def _context_prefix(
    lines: list[str],
    headings: tuple[_Heading, ...],
    heading_index: int,
) -> str:
    frontmatter_body_start = _frontmatter_body_start(lines)
    heading_line_indexes = {heading.line_index for heading in headings}
    context: list[str] = []
    index = heading_index - 1

    while index >= frontmatter_body_start and len(context) < 3:
        line = lines[index]
        if index in heading_line_indexes:
            break
        if line.strip():
            context.append(line)
        index -= 1

    return "\n".join(reversed(context))


def _frontmatter_body_start(lines: list[str]) -> int:
    if not lines or lines[0].strip() != "---":
        return 0
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return index + 1
    return 0


def _next_fence_state(
    match: re.Match[str],
    current: _FenceState | None,
) -> _FenceState | None:
    marker_text = match.group(1)
    marker = marker_text[0]
    length = len(marker_text)
    if current is None:
        return _FenceState(marker=marker, length=length)
    if current.marker == marker and length >= current.length:
        return None
    return current


def _clean_heading_text(text: str) -> str:
    return re.sub(r"\s+#+\s*$", "", text).strip()


def _normalize_heading_name(value: str) -> str:
    return _clean_heading_text(value.lstrip("#").strip()).casefold()


def _validate_limit(limit: int) -> int:
    if not isinstance(limit, int) or limit < 1:
        raise _invalid_request("limit must be a positive integer")
    return min(limit, _MAX_SEARCH_LIMIT)


def _parse_regex_query(query: str) -> _RegexQuery | None:
    if not (len(query) >= 2 and query.startswith("/") and query.endswith("/")):
        return None

    pattern_text = query[1:-1]
    if not pattern_text:
        raise _invalid_request("query is required")

    try:
        pattern = re.compile(pattern_text, flags=re.IGNORECASE)
    except re.error as error:
        raise _invalid_request(f"invalid regex query: {error}") from error

    fts_query = _regex_candidate_query(pattern_text)
    return _RegexQuery(pattern=pattern, fts_query=fts_query)


def _regex_candidate_query(pattern_text: str) -> str:
    without_classes = re.sub(r"\\[A-Za-z]+", " ", pattern_text)
    literalish = re.sub(r"\\(.)", r"\1", without_classes)
    terms = tuple(_query_terms(literalish))
    if not terms:
        raise _invalid_request("regex query must contain at least one literal term")
    return " OR ".join(_quote_fts_term(term) for term in terms)


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

    normalized_tags = tuple(_normalize_tag(tag) for tag in tags)
    for tag in normalized_tags:
        if not tag:
            continue
        where.append("LOWER(blocks.tags) LIKE ? ESCAPE '\\'")
        params.append(f'%"{_escape_like_pattern(tag)}"%')

    include_patterns = tuple(_normalize_glob(path) for path in paths if path.strip())
    if include_patterns:
        where.append(
            "("
            + " OR ".join(
                "vault_path_glob_match(?, blocks.vault_path)" for _ in include_patterns
            )
            + ")"
        )
        params.extend(include_patterns)

    for pattern in (_normalize_glob(path) for path in exclude_paths if path.strip()):
        where.append("NOT vault_path_glob_match(?, blocks.vault_path)")
        params.append(pattern)

    if limit is not None:
        params.append(limit)

    limit_clause = "LIMIT ?" if limit is not None else ""
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
    regex_query: _RegexQuery | None,
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
    regex_query: _RegexQuery | None,
) -> str:
    if regex_query is not None:
        content = row["content"]
        match = regex_query.pattern.search(content)
        if match is not None:
            return _format_preview(content, match.start(), match.end())

    haystack = "\n".join(part for part in (row["heading"], row["content"]) if part)
    for term in _query_terms(query):
        match = re.search(re.escape(term), haystack, flags=re.IGNORECASE)
        if match is not None:
            return _format_preview(haystack, match.start(), match.end())

    return _format_preview(haystack, 0, 0)


def _format_preview(text: str, start: int, end: int) -> str:
    left = max(0, start - _PREVIEW_RADIUS)
    right = min(len(text), max(end + _PREVIEW_RADIUS, _PREVIEW_MIN_LENGTH))
    preview = re.sub(r"\s+", " ", text[left:right]).strip()
    if left > 0:
        preview = f"...{preview}"
    if right < len(text):
        preview = f"{preview}..."
    if len(preview) > _PREVIEW_MAX_LENGTH:
        trim_at = _PREVIEW_MAX_LENGTH - 3
        preview = f"{preview[:trim_at].rstrip()}..."
    return preview


def _query_terms(query: str) -> list[str]:
    return [
        term
        for term in re.findall(r"[A-Za-z0-9_/-]+", query)
        if term.upper() not in _BOOLEAN_TERMS
    ]


def _quote_fts_term(term: str) -> str:
    return '"' + term.replace('"', '""') + '"'


def _normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("#").casefold()


def _register_glob_function(connection: sqlite3.Connection) -> None:
    connection.create_function("vault_path_glob_match", 2, _sqlite_glob_match)


def _sqlite_glob_match(pattern: str | None, vault_path: str | None) -> int:
    if pattern is None or vault_path is None:
        return 0
    return int(_glob_matches(pattern, vault_path))


def _glob_matches(pattern: str, vault_path: str) -> bool:
    normalized_path = vault_path.replace("\\", "/").lstrip("/")
    return (
        _compile_glob_regex(_normalize_glob(pattern)).fullmatch(normalized_path)
        is not None
    )


@lru_cache(maxsize=512)
def _compile_glob_regex(pattern: str) -> re.Pattern[str]:
    return re.compile(_glob_to_regex(pattern))


def _glob_to_regex(pattern: str) -> str:
    normalized = _normalize_glob(pattern)
    pieces: list[str] = ["^"]
    index = 0
    while index < len(normalized):
        if normalized.startswith("**/", index):
            pieces.append("(?:.*/)?")
            index += 3
            continue
        if normalized.startswith("**", index):
            pieces.append(".*")
            index += 2
            continue

        character = normalized[index]
        if character == "*":
            pieces.append("[^/]*")
        elif character == "?":
            pieces.append("[^/]")
        else:
            pieces.append(re.escape(character))
        index += 1
    pieces.append("$")
    return "".join(pieces)


def _normalize_glob(pattern: str) -> str:
    return pattern.replace("\\", "/").lstrip("/")


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
