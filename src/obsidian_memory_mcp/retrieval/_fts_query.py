"""FTS5 MATCH query preparation for indexed search."""

from __future__ import annotations

import re

_INDEXED_COLUMNS = ("heading", "content", "tags", "section_path")
_ADVANCED_FTS_PATTERN = re.compile(
    rf"""
    \b(?:AND|OR|NOT)\b |
    NEAR\s*\( |
    \* |
    ^- |
    (?:^|\s)-\{{ |
    (?:{"|".join(_INDEXED_COLUMNS)})\s*:
    """,
    re.IGNORECASE | re.VERBOSE,
)


def quote_fts_term(term: str) -> str:
    return '"' + term.replace('"', '""') + '"'


def prepare_fts_match_query(query: str) -> str:
    if _is_advanced_fts_query(query):
        return query
    terms = query.split()
    if len(terms) == 1:
        return quote_fts_term(query)
    return " ".join(quote_fts_term(term) for term in terms)


def _is_advanced_fts_query(query: str) -> bool:
    if '"' in query:
        return True
    return _ADVANCED_FTS_PATTERN.search(query) is not None
