"""Shared markdown parsing utilities for read paths and indexing helpers."""

from obsidian_memory_mcp.markdown._fence import (
    FENCE_RE,
    HEADING_RE,
    FenceState,
    is_fence_line,
    next_fence_state,
)
from obsidian_memory_mcp.markdown._frontmatter import (
    FrontmatterParseResult,
    extract_frontmatter,
    parse_frontmatter,
)
from obsidian_memory_mcp.markdown._headings import (
    MarkdownHeading,
    clean_heading_text,
    find_headings,
    matching_heading,
    normalize_heading_name,
    section_end_index,
)

__all__ = [
    "FENCE_RE",
    "HEADING_RE",
    "FenceState",
    "FrontmatterParseResult",
    "MarkdownHeading",
    "clean_heading_text",
    "extract_frontmatter",
    "find_headings",
    "is_fence_line",
    "matching_heading",
    "next_fence_state",
    "normalize_heading_name",
    "parse_frontmatter",
    "section_end_index",
]
