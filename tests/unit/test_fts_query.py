from __future__ import annotations

import pytest

from obsidian_memory_mcp.retrieval._fts_query import prepare_fts_match_query, quote_fts_term


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("databricks-scan-api", '"databricks-scan-api"'),
        ("complex query", '"complex query"'),
        ("compliance", '"compliance"'),
    ],
)
def test_prepare_fts_match_query_quotes_plain_text(query: str, expected: str) -> None:
    assert prepare_fts_match_query(query) == expected


@pytest.mark.parametrize(
    "query",
    [
        '"already quoted"',
        "compliance AND governance",
        "heading:compliance",
        "content:needle OR tags:api",
        "NEAR(a b)",
        "prefix*",
        "-heading:deprecated",
        "- {heading content} : term",
    ],
)
def test_prepare_fts_match_query_passes_through_advanced_fts(query: str) -> None:
    assert prepare_fts_match_query(query) == query


def test_prepare_fts_match_query_passes_through_malformed_operator_only() -> None:
    assert prepare_fts_match_query("AND") == "AND"


def test_quote_fts_term_escapes_embedded_double_quotes() -> None:
    assert quote_fts_term('say "hello"') == '"say ""hello"""'
