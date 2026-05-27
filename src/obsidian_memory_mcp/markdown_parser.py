"""Shared markdown heading parsing helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
_FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$")


@dataclass(frozen=True)
class MarkdownHeading:
    line_index: int
    level: int
    text: str


@dataclass(frozen=True)
class _FenceState:
    marker: str
    length: int


def find_headings(lines: list[str]) -> tuple[MarkdownHeading, ...]:
    headings: list[MarkdownHeading] = []
    fence_state: _FenceState | None = None

    for index, line in enumerate(lines):
        fence_match = _FENCE_RE.match(line)
        if fence_match is not None:
            fence_state = _next_fence_state(fence_match, fence_state)
            continue
        if fence_state is not None:
            continue

        heading_match = _HEADING_RE.match(line)
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


def _next_fence_state(
    match: re.Match[str],
    current: _FenceState | None,
) -> _FenceState | None:
    marker_text = match.group(1)
    suffix = match.group(2).strip()
    marker = marker_text[0]
    length = len(marker_text)
    if current is None:
        return _FenceState(marker=marker, length=length)
    if current.marker == marker and length >= current.length and not suffix:
        return None
    return current
