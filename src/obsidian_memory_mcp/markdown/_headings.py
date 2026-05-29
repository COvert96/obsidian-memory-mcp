"""Read-time heading discovery and section boundaries."""

from __future__ import annotations

import re
from dataclasses import dataclass

from obsidian_memory_mcp.markdown._fence import HEADING_RE, next_fence_state


@dataclass(frozen=True)
class MarkdownHeading:
    line_index: int
    level: int
    text: str


def find_headings(lines: list[str]) -> tuple[MarkdownHeading, ...]:
    headings: list[MarkdownHeading] = []
    fence_state = None

    for index, line in enumerate(lines):
        fence_state = next_fence_state(line, fence_state)
        if fence_state is not None:
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match is None:
            continue

        headings.append(
            MarkdownHeading(
                line_index=index,
                level=len(heading_match.group(1)),
                text=clean_heading_text(heading_match.group(2)),
            )
        )

    return tuple(headings)


def matching_heading(
    headings: tuple[MarkdownHeading, ...],
    heading_name: str,
) -> MarkdownHeading | None:
    target = normalize_heading_name(heading_name)
    return next(
        (
            heading
            for heading in headings
            if normalize_heading_name(heading.text) == target
        ),
        None,
    )


def section_end_index(
    headings: tuple[MarkdownHeading, ...],
    current: MarkdownHeading,
    *,
    line_count: int,
) -> int:
    for heading in headings:
        if heading.line_index > current.line_index and heading.level <= current.level:
            return heading.line_index
    return line_count


def clean_heading_text(text: str) -> str:
    return re.sub(r"\s+#+\s*$", "", text).strip()


def normalize_heading_name(value: str) -> str:
    return clean_heading_text(value.lstrip("#").strip()).casefold()
