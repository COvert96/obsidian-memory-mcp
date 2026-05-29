"""Tag filtering for context-pack document candidates."""

from __future__ import annotations

from obsidian_memory_mcp.markdown import parse_frontmatter, tag_values_from_field


def matches_tags(content: str, tags_filter: tuple[str, ...]) -> bool:
    if not tags_filter:
        return True
    available = frontmatter_tags(content)
    required = {normalize_tag(tag) for tag in tags_filter}
    return required.issubset(available)


def frontmatter_tags(content: str) -> set[str]:
    values = tag_values_from_field(parse_frontmatter(content).get("tags"))
    return {normalize_tag(tag) for tag in values}


def normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("#").casefold()
