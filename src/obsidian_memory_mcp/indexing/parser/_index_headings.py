"""Heading discovery for indexing."""

from __future__ import annotations

from obsidian_memory_mcp.markdown import HEADING_RE, is_fence_line, next_fence_state
from obsidian_memory_mcp.indexing.parser._models import HeadingOccurrence
from obsidian_memory_mcp.indexing.parser._text import (
    clean_heading_text,
    section_key,
    slugify,
)


def find_headings(
    vault_path: str,
    body_lines: list[str],
    body_start_line: int,
) -> tuple[HeadingOccurrence, ...]:
    headings: list[HeadingOccurrence] = []
    slug_counts: dict[str, int] = {}
    heading_stack: list[tuple[int, str]] = []
    fence_state = None

    for index, line in enumerate(body_lines):
        fence_state = next_fence_state(line, fence_state)
        if fence_state is not None and is_fence_line(line):
            continue
        if fence_state is not None:
            continue

        match = HEADING_RE.match(line)
        if match is None:
            continue

        level = len(match.group(1))
        text = clean_heading_text(match.group(2))
        slug = slugify(text)
        ordinal = slug_counts.get(slug, 0) + 1
        slug_counts[slug] = ordinal
        section_key_value = section_key(vault_path, slug, ordinal)
        heading_stack = [item for item in heading_stack if item[0] < level]
        heading_stack.append((level, text))
        headings.append(
            HeadingOccurrence(
                level=level,
                text=text,
                slug=slug,
                ordinal=ordinal,
                section_key=section_key_value,
                body_line_index=index,
                line_number=body_start_line + index,
                section_path=" > ".join(item[1] for item in heading_stack),
            )
        )

    return tuple(headings)
