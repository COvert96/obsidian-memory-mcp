"""Tag extraction for indexing."""

from __future__ import annotations

import re
from typing import Any

from obsidian_memory_mcp.markdown import is_fence_line, next_fence_state

_MARKDOWN_TAG_RE = re.compile(r"(?<![\w/])#([A-Za-z0-9][A-Za-z0-9_/-]*)")
_INLINE_CODE_RE = re.compile(r"`[^`]*`")


def extract_tags(
    frontmatter: dict[str, Any], body_lines: list[str]
) -> tuple[str, ...]:
    tags: set[str] = set()
    tags.update(_frontmatter_tags(frontmatter.get("tags")))

    for line in _non_code_lines(body_lines):
        cleaned = _INLINE_CODE_RE.sub("", line)
        for match in _MARKDOWN_TAG_RE.finditer(cleaned):
            tags.add(_normalize_tag(match.group(1)))

    return tuple(sorted(tag for tag in tags if tag))


def _frontmatter_tags(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {
            _normalize_tag(part) for part in re.split(r"[\s,]+", value) if part.strip()
        }
    if isinstance(value, (list, tuple)):
        return {_normalize_tag(str(part)) for part in value if str(part).strip()}
    return {_normalize_tag(str(value))}


def _non_code_lines(lines: list[str]) -> tuple[str, ...]:
    result: list[str] = []
    fence_state = None
    for line in lines:
        if is_fence_line(line):
            fence_state = next_fence_state(line, fence_state)
            continue
        if fence_state is None:
            result.append(line)
    return tuple(result)


def _normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("#").strip()
