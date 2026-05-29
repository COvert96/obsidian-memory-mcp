"""Tag filtering for context-pack document candidates."""

from __future__ import annotations

import re

from obsidian_memory_mcp.markdown import parse_frontmatter


def matches_tags(content: str, tags_filter: tuple[str, ...]) -> bool:
    if not tags_filter:
        return True
    available = frontmatter_tags(content)
    required = {normalize_tag(tag) for tag in tags_filter}
    return required.issubset(available)


def frontmatter_tags(content: str) -> set[str]:
    value = parse_frontmatter(content).get("tags")
    if value is None:
        return set()
    if isinstance(value, str):
        return {
            normalize_tag(part) for part in re.split(r"[\s,]+", value) if part.strip()
        }
    if isinstance(value, (list, tuple)):
        return {normalize_tag(str(part)) for part in value if str(part).strip()}
    return {normalize_tag(str(value))}


def normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("#").casefold()
