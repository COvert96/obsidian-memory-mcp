"""Markdown parsing policy for deterministic vault indexing.

Indexing-only: block boundaries, FTS token targets, and wikilink extraction.
For read-time section slicing and frontmatter use the ``markdown`` package.
"""

from __future__ import annotations

from typing import Any

from obsidian_memory_mcp.markdown import extract_frontmatter as _markdown_extract_frontmatter
from obsidian_memory_mcp.indexing.parser._blocks import build_blocks
from obsidian_memory_mcp.indexing.parser._index_headings import find_headings
from obsidian_memory_mcp.indexing.parser._models import (
    HARD_BLOCK_MAX_TOKENS,
    PARSER_VERSION,
    TARGET_BLOCK_MAX_TOKENS,
    TARGET_BLOCK_MIN_TOKENS,
    ParsedBlock,
    ParsedHeading,
    ParsedNote,
    ParsedSection,
    ParsedWikilink,
)
from obsidian_memory_mcp.indexing.parser._sections import build_sections
from obsidian_memory_mcp.indexing.parser._tags import extract_tags
from obsidian_memory_mcp.indexing.parser._text import (
    estimate_markdown_tokens,
    normalize_newlines,
    sha256,
)
from obsidian_memory_mcp.indexing.parser._wikilinks import extract_wikilinks

__all__ = [
    "HARD_BLOCK_MAX_TOKENS",
    "PARSER_VERSION",
    "TARGET_BLOCK_MAX_TOKENS",
    "TARGET_BLOCK_MIN_TOKENS",
    "ParsedBlock",
    "ParsedHeading",
    "ParsedNote",
    "ParsedSection",
    "ParsedWikilink",
    "estimate_markdown_tokens",
    "parse_markdown",
    "parse_markdown_bytes",
]


def _extract_frontmatter(
    content: str,
) -> tuple[dict[str, Any], str | None, str, int]:
    result = _markdown_extract_frontmatter(content)
    return result.frontmatter, result.error, result.body, result.body_start_line


def parse_markdown(
    *,
    vault_path: str,
    content: str | bytes,
    parser_version: str = PARSER_VERSION,
) -> ParsedNote:
    raw_bytes = content if isinstance(content, bytes) else content.encode("utf-8")
    text = raw_bytes.decode("utf-8")
    normalized_text = normalize_newlines(text)
    frontmatter, frontmatter_error, body, body_start_line = _extract_frontmatter(
        normalized_text
    )
    body_lines = body.split("\n")
    note_tags = extract_tags(frontmatter, body_lines)
    headings = find_headings(vault_path, body_lines, body_start_line)
    sections = build_sections(
        vault_path, body_lines, body_start_line, headings, note_tags
    )
    blocks = tuple(block for section in sections for block in build_blocks(section))
    wikilinks = tuple(
        link for section in sections for link in extract_wikilinks(vault_path, section)
    )

    return ParsedNote(
        vault_path=vault_path,
        frontmatter=frontmatter,
        frontmatter_parse_error=frontmatter_error,
        headings=tuple(
            ParsedHeading(
                level=heading.level,
                text=heading.text,
                slug=heading.slug,
                ordinal=heading.ordinal,
                section_key=heading.section_key,
                line_number=heading.line_number,
            )
            for heading in headings
        ),
        sections=sections,
        blocks=blocks,
        wikilinks=wikilinks,
        tags=note_tags,
        raw_content_hash=sha256(raw_bytes),
        normalized_content_hash=sha256(normalized_text.encode("utf-8")),
        parser_version=parser_version,
    )


def parse_markdown_bytes(
    *,
    vault_path: str,
    content: bytes,
    parser_version: str = PARSER_VERSION,
) -> ParsedNote:
    return parse_markdown(
        vault_path=vault_path, content=content, parser_version=parser_version
    )
