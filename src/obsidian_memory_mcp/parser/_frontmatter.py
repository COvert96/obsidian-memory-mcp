"""Frontmatter extraction for indexing."""

from __future__ import annotations

from typing import Any

from obsidian_memory_mcp.markdown import extract_frontmatter as _extract


def extract_frontmatter(content: str) -> tuple[dict[str, Any], str | None, str, int]:
    result = _extract(content)
    return result.frontmatter, result.error, result.body, result.body_start_line
