"""Formatting helpers for search previews."""

from __future__ import annotations

import re

_PREVIEW_RADIUS = 80
_PREVIEW_MIN_LENGTH = 180
_PREVIEW_MAX_LENGTH = 200


def format_preview(text: str, start: int, end: int) -> str:
    left = max(0, start - _PREVIEW_RADIUS)
    right = min(len(text), max(end + _PREVIEW_RADIUS, _PREVIEW_MIN_LENGTH))
    preview = re.sub(r"\s+", " ", text[left:right]).strip()
    if left > 0:
        preview = f"...{preview}"
    if right < len(text):
        preview = f"{preview}..."
    if len(preview) > _PREVIEW_MAX_LENGTH:
        trim_at = _PREVIEW_MAX_LENGTH - 3
        preview = f"{preview[:trim_at].rstrip()}..."
    return preview

