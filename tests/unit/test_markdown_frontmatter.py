from __future__ import annotations

from obsidian_memory_mcp.markdown import (
    extract_frontmatter,
    parse_frontmatter,
)
from obsidian_memory_mcp.indexing.parser import _extract_frontmatter as index_extract


def test_parse_frontmatter_matches_indexing_helper() -> None:
    content = "---\ntype: concept\ntags: [alpha]\n---\n# Title\nBody\n"

    expected = {"type": "concept", "tags": ["alpha"]}
    assert parse_frontmatter(content) == expected

    indexed = index_extract(content)
    assert indexed[0] == expected
    assert indexed[1] is None
    assert indexed[2] == "# Title\nBody\n"


def test_extract_frontmatter_reports_yaml_errors_for_indexing() -> None:
    content = "---\n: broken\n---\n# Title\n"

    result = extract_frontmatter(content)

    assert result.frontmatter == {}
    assert result.error is not None
    assert "malformed YAML" in result.error
    assert parse_frontmatter(content) == {}
