"""Regex-query support for deterministic FTS search.

The main `SearchService` accepts both plain-text FTS queries and regex queries in
the form `/pattern/`. Regex queries are executed in two phases:

1. A permissive FTS query is built from literal-ish terms extracted from the
   regex pattern.
2. Results are post-filtered using the compiled regex.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from obsidian_memory_mcp.errors import ErrorCode, ToolExecutionError, build_error

_BOOLEAN_TERMS = frozenset({"AND", "OR", "NOT"})
_MAX_SEARCH_LIMIT = 100


@dataclass(frozen=True)
class RegexQuery:
    pattern: re.Pattern[str]
    fts_query: str


def validate_limit(limit: int) -> int:
    if not isinstance(limit, int) or limit < 1:
        raise _invalid_request("limit must be a positive integer")
    return min(limit, _MAX_SEARCH_LIMIT)


def parse_regex_query(query: str) -> RegexQuery | None:
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
    return RegexQuery(pattern=pattern, fts_query=fts_query)


def _regex_candidate_query(pattern_text: str) -> str:
    without_classes = re.sub(r"\\[A-Za-z]+", " ", pattern_text)
    literalish = re.sub(r"\\(.)", r"\1", without_classes)
    terms = tuple(query_terms(literalish))
    if not terms:
        raise _invalid_request("regex query must contain at least one literal term")
    return " OR ".join(_quote_fts_term(term) for term in terms)


def query_terms(query: str) -> list[str]:
    return [
        term
        for term in re.findall(r"[A-Za-z0-9_/-]+", query)
        if term.upper() not in _BOOLEAN_TERMS
    ]


def _quote_fts_term(term: str) -> str:
    return '"' + term.replace('"', '""') + '"'


def _invalid_request(message: str) -> ToolExecutionError:
    return ToolExecutionError(build_error(ErrorCode.ERR_INVALID_REQUEST, message=message))

