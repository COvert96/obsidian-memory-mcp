"""Fence-line state and heading regex for markdown scans."""

from __future__ import annotations

import re
from dataclasses import dataclass

FENCE_RE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$")
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")


@dataclass(frozen=True)
class FenceState:
    marker: str
    length: int


def next_fence_state(line: str, current: FenceState | None) -> FenceState | None:
    match = FENCE_RE.match(line)
    if match is None:
        return current

    marker_text = match.group(1)
    suffix = match.group(2).strip()
    marker = marker_text[0]
    length = len(marker_text)
    if current is None:
        return FenceState(marker=marker, length=length)
    if current.marker == marker and length >= current.length and not suffix:
        return None
    return current


def is_fence_line(line: str) -> bool:
    return FENCE_RE.match(line) is not None
